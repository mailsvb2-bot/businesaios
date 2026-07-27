from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

import core.retention.arms as arms_mod
import core.retention.engine as engine_mod
import core.retention.pricing_flow as pricing_mod
import core.policies.telegram.unified_policy as unified_mod
from application.decision_policy.policy_stage import propose_action
from core.ai.action_ranking import rank_proposals, score_proposal
from core.policies.telegram.helpers import ProposedAction, normalize_proposed_action, propose
from core.policies.telegram.retention_integration import (
    apply_retention_constraints_to_state,
    merge_retention_plan,
)
from core.retention.arms import RetentionArmEvidence
from core.retention.bandit import choose_arm, update_arm
from core.retention.decision_adapter import RetentionDecisionAdapter
from core.retention.decision_adapter_support import (
    build_offer_proposal,
    merge_inline_keyboards,
)
from core.retention.engine import (
    RetentionEvaluation,
    RetentionOfferCandidate,
    materialize_candidate,
    neutral_decision,
)
from core.retention.pricing_flow import RetentionPriceEvidence
from runtime._internal.effects_actions.telegram.messaging_parts.tracking import (
    track_business_event,
)


class FakeStore:
    def __init__(self, events: list[dict[str, Any]] | None = None) -> None:
        self.events = list(events or [])
        self.updated: list[tuple[str, bool]] = []
        self.ensure_calls = 0
        self.feature_writes = 0
        self.bandits: dict[str, tuple[Any, Any]] = {}

    def iter_events(self, **kwargs: Any):
        del kwargs
        return iter(self.events)

    def latest_events(self, **kwargs: Any):
        event_type = kwargs.get("event_type")
        return [
            event
            for event in self.events
            if event_type is None or event.get("event_type") == event_type
        ]

    def bandit_get_arm(self, *, tenant_id: str, arm: str):
        del tenant_id
        return self.bandits.get(arm, (1, 1))

    def bandit_ensure_arm(self, **kwargs: Any) -> None:
        del kwargs
        self.ensure_calls += 1

    def bandit_update_arm(self, *, tenant_id: str, arm: str, success: bool, now_ms: int):
        del tenant_id, now_ms
        self.updated.append((arm, success))

    def upsert_user_features_daily(self, **kwargs: Any) -> None:
        del kwargs
        self.feature_writes += 1


@dataclass(frozen=True)
class FakeState:
    schema_version: int = 1
    user: dict[str, Any] = field(default_factory=dict)
    session: dict[str, Any] = field(default_factory=dict)
    product: dict[str, Any] = field(default_factory=dict)
    economy: dict[str, Any] = field(default_factory=dict)
    timestamp_ms: int = 1_000_000
    tenant_id: str = "tenant-a"
    user_id: str | None = "user-a"
    price_constraints: dict[str, Any] | None = None
    telegram_update: dict[str, Any] | None = field(
        default_factory=lambda: {"message": {"chat": {"id": 11}}}
    )


def candidate(
    ident: str = "c1",
    *,
    arm: str = "offer_30_14900",
    price: int = 14_900,
    profit: float = 1000.0,
) -> RetentionOfferCandidate:
    return RetentionOfferCandidate(
        candidate_id=ident,
        offer_arm=arm,
        offer_price_rub=price,
        expected_profit_delta_minor=profit,
        ope_wis=0.6,
        uplift=0.7,
        risk_penalty=0.1,
        propensity=0.5,
        debug={"source": "test"},
    )


def evaluation(*items: RetentionOfferCandidate, suppressed: bool = False) -> RetentionEvaluation:
    return RetentionEvaluation(
        tenant_id="tenant-a",
        day_key="2026-01-10",
        day_index=10,
        hazard=0.1,
        readiness=0.7,
        suppressed=suppressed,
        reason="suppressed" if suppressed else "candidates_ready",
        candidates=tuple(items),
        debug={"features": {"x": 1.0}, "no_second_brain": True},
    )


class FakeOfferEngine:
    def should_show_offer(self, **_kwargs: Any):
        return True, {"reason": "ok"}

    def render_offer(self, **kwargs: Any):
        return SimpleNamespace(
            text=f"Оффер за {kwargs['price_rub']} ₽",
            variant="a",
            price_rub=kwargs["price_rub"],
            meta={
                "reply_markup": {
                    "inline_keyboard": [[{"text": "Купить", "callback_data": "buy"}]]
                }
            },
        )


class FakeCooldown:
    def __init__(self) -> None:
        self.marks = 0

    def get_last_shown_ms(self, **_kwargs: Any):
        return None

    def mark_shown_now(self, **_kwargs: Any) -> None:
        self.marks += 1


def test_legacy_offer_renderer_is_explicit_and_read_only(monkeypatch) -> None:
    import core.retention.decision_adapter_support as support

    none_decision = neutral_decision(evaluation())
    assert support.try_build_offer_step(
        decision=none_decision,
        state=FakeState(),
        offer_engine=FakeOfferEngine(),
        cooldown_store=FakeCooldown(),
        user_id="u",
    ) == (None, None)

    selected = materialize_candidate(evaluation(candidate()), candidate_id="c1")
    missing_tenant = FakeState(tenant_id="default")
    missing = RetentionEvaluation(
        tenant_id="",
        day_key="d",
        day_index=1,
        hazard=0.1,
        readiness=0.8,
        suppressed=False,
        reason="x",
        candidates=(candidate(),),
        debug={},
    )
    selected_missing = materialize_candidate(missing, candidate_id="c1")
    step, debug = support.try_build_offer_step(
        decision=selected_missing,
        state=missing_tenant,
        offer_engine=FakeOfferEngine(),
        cooldown_store=None,
        user_id="u",
    )
    assert step is None and debug["constraints"]["reason"] == "missing_tenant_id"

    safe_state = FakeState(
        price_constraints={
            "mode": "safe",
            "disallow_offer_prefixes": ["offer_"],
            "reason": "owner_safe",
        }
    )
    step, debug = support.try_build_offer_step(
        decision=selected,
        state=safe_state,
        offer_engine=FakeOfferEngine(),
        cooldown_store=None,
        user_id="u",
    )
    assert step is None and debug["constraints"]["reason"] == "owner_safe"

    monkeypatch.setattr(support, "offer_allowed", lambda **_kwargs: False)
    assert support.try_build_offer_step(
        decision=selected,
        state=FakeState(),
        offer_engine=FakeOfferEngine(),
        cooldown_store=None,
        user_id="u",
    ) == (None, None)
    monkeypatch.setattr(support, "offer_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(
        support,
        "render_offer_step",
        lambda **_kwargs: ({"track_payload": {"x": 1}}, {}),
    )
    monkeypatch.setattr(support, "decorate_retention_payload", lambda **kwargs: kwargs["payload"])
    step, debug = support.try_build_offer_step(
        decision=selected,
        state=FakeState(),
        offer_engine=FakeOfferEngine(),
        cooldown_store=None,
        user_id="u",
    )
    assert step["track_payload"] == {"x": 1} and debug is None


def test_pricing_all_fallbacks_base_restore_and_stoploss(monkeypatch) -> None:
    store = FakeStore()
    enabled_int = lambda name, default: 1 if name == "PRICING_RL_ENABLED" else default
    env_float = lambda _name, default: default

    monkeypatch.setattr(
        pricing_mod,
        "collect_pricing_evidence",
        lambda **_kwargs: ({}, {"trials": 0, "successes": 0}),
    )
    rows = pricing_mod.build_price_candidates(
        store=store,
        tenant_id="t",
        offer_arm="a",
        base_price_rub=100,
        now_ms=100,
        pricing_ctx="",
        env_int=enabled_int,
        env_float=env_float,
    )
    assert rows[0].debug["note"] == "no_trials"

    monkeypatch.setattr(
        pricing_mod,
        "collect_pricing_evidence",
        lambda **_kwargs: ({100: (2, 0)}, {"trials": 2, "successes": 0}),
    )
    assert pricing_mod.build_price_candidates(
        store=store,
        tenant_id="t",
        offer_arm="a",
        base_price_rub=100,
        now_ms=100,
        pricing_ctx="",
        env_int=enabled_int,
        env_float=env_float,
    )[0].debug["note"] == "no_successes"

    monkeypatch.setattr(
        pricing_mod,
        "collect_pricing_evidence",
        lambda **_kwargs: ({100: (2, 1)}, {"trials": 2, "successes": 1}),
    )
    monkeypatch.setattr(pricing_mod, "build_candidates", lambda **_kwargs: [])
    assert pricing_mod.build_price_candidates(
        store=store,
        tenant_id="t",
        offer_arm="a",
        base_price_rub=100,
        now_ms=100,
        pricing_ctx="",
        env_int=enabled_int,
        env_float=env_float,
    )[0].debug["note"] == "single_candidate"

    monkeypatch.setattr(pricing_mod, "build_candidates", lambda **_kwargs: [120, 130])
    monkeypatch.setattr(pricing_mod, "posterior_mean_conv", lambda **_kwargs: 0.1)
    monkeypatch.setattr(pricing_mod, "choose_probabilities", lambda **_kwargs: [0.4, 0.6])
    monkeypatch.setattr(
        pricing_mod,
        "should_apply_price",
        lambda *_args, **_kwargs: (True, {"ok": True}),
    )
    restored = pricing_mod.build_price_candidates(
        store=store,
        tenant_id="t",
        offer_arm="a",
        base_price_rub=100,
        now_ms=100,
        pricing_ctx="",
        env_int=enabled_int,
        env_float=env_float,
    )
    assert [row.price_rub for row in restored] == [120, 130, 100]
    assert restored[-1].debug["note"] == "base_restored"

    monkeypatch.setattr(
        pricing_mod,
        "should_apply_price",
        lambda *_args, **_kwargs: (False, {"blocked": True}),
    )
    filtered = pricing_mod.build_price_candidates(
        store=store,
        tenant_id="t",
        offer_arm="a",
        base_price_rub=100,
        now_ms=100,
        pricing_ctx="",
        env_int=enabled_int,
        env_float=env_float,
    )
    assert filtered[0].debug["note"] == "stoploss_filtered"

    debug: dict[str, Any] = {}
    assert pricing_mod.apply_stoploss(
        store=store,
        tenant_id="t",
        user_id="u",
        offer_arm="a",
        base_price_rub=None,
        current_price_rub=100,
        now_ms=1,
        pricing_ctx="",
        env_int=lambda _name, default: default,
        env_float=env_float,
        debug=debug,
    ) == (100, debug)
    assert pricing_mod.apply_stoploss(
        store=store,
        tenant_id="t",
        user_id="u",
        offer_arm="a",
        base_price_rub=100,
        current_price_rub=120,
        now_ms=1,
        pricing_ctx="",
        env_int=lambda _name, default: default,
        env_float=env_float,
        debug={},
    )[0] == 100

    monkeypatch.setattr(
        pricing_mod,
        "should_apply_price",
        lambda *_args, **_kwargs: (True, {"allowed": True}),
    )
    assert pricing_mod.apply_stoploss(
        store=store,
        tenant_id="t",
        user_id="u",
        offer_arm="a",
        base_price_rub=100,
        current_price_rub=120,
        now_ms=1,
        pricing_ctx="web",
        env_int=lambda _name, default: default,
        env_float=env_float,
        debug={},
    )[0] == 120
    monkeypatch.setattr(
        pricing_mod,
        "_stoploss_config",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError()),
    )
    monkeypatch.setattr(pricing_mod, "exception_throttled", lambda *_args, **_kwargs: None)
    assert pricing_mod.apply_stoploss(
        store=store,
        tenant_id="t",
        user_id="u",
        offer_arm="a",
        base_price_rub=100,
        current_price_rub=120,
        now_ms=1,
        pricing_ctx="",
        env_int=lambda _name, default: default,
        env_float=env_float,
        debug={},
    )[0] == 120


def test_engine_class_sandbox_normal_and_explicit_materialization(monkeypatch) -> None:
    store = FakeStore()
    engine = engine_mod.RetentionEngine(store, tenant_id="tenant-a")
    assert engine.tenant_id == "tenant-a"
    monkeypatch.setattr(engine_mod, "is_retention_allowed", lambda **_kwargs: False)
    sandbox = engine.compute_evidence(user_id="u")
    assert sandbox.suppressed and sandbox.reason == "sandbox"

    expected = evaluation(candidate())
    monkeypatch.setattr(engine_mod, "is_retention_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(engine_mod, "evaluate_for_day", lambda *_args, **_kwargs: expected)
    assert engine.compute_evidence(user_id="u") is expected
    assert engine.compute_decision(user_id="u").offer_arm == "NONE"
    assert engine.decide_offer(tenant_id="other", user_id="u", context={}) is None
    assert engine.decide_offer(tenant_id="tenant-a", user_id="u", context={}) is None
    monkeypatch.setattr(engine, "compute_evidence", lambda **_kwargs: expected)
    materialized = engine.decide_offer(
        tenant_id="tenant-a",
        user_id="u",
        context={"selected_candidate_id": "c1", "day_key": "d", "day_index": 1},
    )
    assert materialized.offer_id == "offer:offer_30_14900"
    assert materialized.score == 1000.0
    unknown = engine_mod.RetentionEngine(store, tenant_id="")
    assert unknown.decide_offer(tenant_id="x", user_id="u", context={}) is None


def test_engine_outbound_daily_and_zero_revenue_fallback(monkeypatch) -> None:
    store = FakeStore()
    monkeypatch.setattr(engine_mod.fx_mod, "compute_features_for_day", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(engine_mod, "estimate_hazard", lambda _features: 0.1)
    monkeypatch.setattr(engine_mod, "estimate_readiness", lambda _features: 0.8)
    monkeypatch.setattr(engine_mod, "should_suppress_marketing", lambda **_kwargs: False)
    monkeypatch.setattr(engine_mod, "has_active_entitlement", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(engine_mod, "is_outbound_overloaded", lambda *_args, **_kwargs: True)
    assert engine_mod.evaluate_for_day(
        store, tenant_id="t", user_id="u", day_key="d", day_index=1, now_ms=1
    ).reason == "outbound_overload"
    monkeypatch.setattr(engine_mod, "is_outbound_overloaded", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(engine_mod, "daily_offer_cap_reached", lambda *_args, **_kwargs: True)
    assert engine_mod.evaluate_for_day(
        store, tenant_id="t", user_id="u", day_key="d", day_index=1, now_ms=1
    ).reason == "daily_cap"

    arm = RetentionArmEvidence("a", 1, 1, 1, 0.5, 0.5, 0, 0, "bandit_state")
    monkeypatch.setattr(
        engine_mod,
        "base_price_for_arm",
        lambda *_args, **_kwargs: 100,
    )
    monkeypatch.setattr(
        engine_mod,
        "build_price_candidates",
        lambda **_kwargs: [RetentionPriceEvidence(100, 0, 0, None, True, True, {})],
    )
    rows = engine_mod._offer_candidates(
        store=store,
        tenant_id="t",
        user_id="u",
        day_key="d",
        now_ms=1,
        readiness=0.8,
        hazard=0.1,
        arms=[arm],
        prices=None,
        outbound_telemetry=None,
    )
    assert rows[0].expected_profit_delta_minor > 0
    assert engine_mod._now_ms() > 0
