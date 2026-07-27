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


def test_arm_evidence_is_deterministic_read_only_and_event_sourced() -> None:
    store = FakeStore(
        [
            {"event_type": "other"},
            {"event_type": "offer_outcome", "payload": "bad-json"},
            {"event_type": "offer_outcome", "payload": {"arm": "a", "success": True}},
            {"event_type": "offer_outcome", "payload": '{"offer_arm":"a","success":false}'},
            {"event_type": "offer_outcome", "payload": {"arm": "", "success": True}},
        ]
    )
    store.bandits = {"a": (99, 1), "b": ("bad", float("nan"))}
    rows = arms_mod.score_arm_candidates_event_sourced(
        store,
        tenant_id="t",
        user_id="u",
        arms=[("a", 2.0), ("b", 4.0)],
        now_ms=100,
    )
    assert [(row.arm, row.source) for row in rows] == [
        ("a", "event_stream"),
        ("b", "bandit_state"),
    ]
    assert rows[0].alpha == 2.0 and rows[0].beta == 2.0
    assert rows[1].posterior_mean == 0.5
    assert store.ensure_calls == 0
    assert arms_mod.score_arm_candidates_event_sourced(
        store,
        tenant_id="t",
        user_id="u",
        arms=[],
        now_ms=100,
    ) == []
    with pytest.raises(ValueError, match="profit_must_be_finite"):
        arms_mod.score_arm_candidates_event_sourced(
            store,
            tenant_id="t",
            user_id="u",
            arms=[("a", float("inf"))],
            now_ms=100,
        )


def test_retention_bandit_selection_is_locked_but_outcomes_still_update() -> None:
    store = FakeStore()
    assert choose_arm(store, tenant_id="t", arms=[]) == "NONE"
    with pytest.raises(RuntimeError, match="requires_decision_core"):
        choose_arm(store, tenant_id="t", arms=[("a", 1.0)])
    update_arm(store, tenant_id="t", arm="NONE", success=True)
    update_arm(store, tenant_id="t", arm="a", success=False, now_ms=7)
    assert store.updated == [("a", False)]


def test_arm_window_filtering_and_base_prices(monkeypatch) -> None:
    failures: list[str] = []
    monkeypatch.setattr(arms_mod, "exception_throttled", lambda _log, *, key, msg: failures.append(key))
    now = 1_000_000
    store = FakeStore(
        [
            {"event_type": "other"},
            {"event_type": "offer_shown", "payload": {"arm": "other"}},
            {
                "event_type": "offer_shown",
                "payload": {"arm": "offer_30_14900", "day_index": "bad"},
                "timestamp_ms": "bad",
            },
        ]
    )
    debug: dict[str, Any] = {}
    assert arms_mod.filter_candidate_arms(
        store,
        tenant_id="t",
        user_id="u",
        candidates=[("unknown", 1.0), ("offer_30_14900", 1.0)],
        now_ms=now,
        debug=debug,
        logger=object(),
    ) == [("unknown", 1.0), ("offer_30_14900", 1.0)]
    assert len(failures) == 2
    shown = FakeStore(
        [{"event_type": "offer_shown", "payload": {"arm": "offer_30_14900", "day_index": 10}}]
    )
    assert arms_mod.filter_candidate_arms(
        shown,
        tenant_id="t",
        user_id="u",
        candidates=[("offer_30_14900", 1.0)],
        now_ms=now,
        debug=debug,
    ) == []
    assert debug["anti_spam"]["offer_30_14900"] == "already_shown_in_window"
    built, marker = arms_mod.build_candidates(day_index=40)
    assert marker is None and len(built) == 3
    assert arms_mod.base_price_for_arm("offer_30_14900", {"p30": 123}) == 123
    assert arms_mod.base_price_for_arm("unknown") is None


def test_pricing_candidates_are_evidence_not_choice(monkeypatch) -> None:
    store = FakeStore()
    assert pricing_mod.build_price_candidates(
        store=store,
        tenant_id="t",
        offer_arm="a",
        base_price_rub=None,
        now_ms=100,
        pricing_ctx="",
        env_int=lambda _name, default: default,
        env_float=lambda _name, default: default,
    ) == []
    disabled = pricing_mod.build_price_candidates(
        store=store,
        tenant_id="t",
        offer_arm="a",
        base_price_rub=100,
        now_ms=100,
        pricing_ctx="web",
        env_int=lambda _name, default: 0 if _name == "PRICING_RL_ENABLED" else default,
        env_float=lambda _name, default: default,
    )
    assert [item.price_rub for item in disabled] == [100]
    assert disabled[0].debug["note"] == "disabled"

    monkeypatch.setattr(
        pricing_mod,
        "collect_pricing_evidence",
        lambda **_kwargs: ({100: (20, 5), 120: (20, 6)}, {"trials": 40, "successes": 11}),
    )
    monkeypatch.setattr(pricing_mod, "build_candidates", lambda **_kwargs: [100, 120])
    monkeypatch.setattr(pricing_mod, "posterior_mean_conv", lambda *, price, **_kwargs: price / 1000)
    monkeypatch.setattr(pricing_mod, "choose_probabilities", lambda **_kwargs: [0.4, 0.6])
    monkeypatch.setattr(
        pricing_mod,
        "should_apply_price",
        lambda *_args, candidate_price_rub, **_kwargs: (candidate_price_rub == 100, {"checked": True}),
    )
    enabled = pricing_mod.build_price_candidates(
        store=store,
        tenant_id="t",
        offer_arm="a",
        base_price_rub=100,
        now_ms=100,
        pricing_ctx="web",
        env_int=lambda name, default: 1 if name == "PRICING_RL_ENABLED" else default,
        env_float=lambda _name, default: default,
    )
    assert [item.price_rub for item in enabled] == [100]
    debug: dict[str, Any] = {}
    assert pricing_mod.maybe_apply_rl_price(
        store=store,
        tenant_id="t",
        user_id="u",
        offer_arm="a",
        base_price_rub=100,
        now_ms=100,
        pricing_ctx="web",
        env_int=lambda name, default: 1 if name == "PRICING_RL_ENABLED" else default,
        env_float=lambda _name, default: default,
        debug=debug,
    ) == 100
    assert debug["pricing_candidates"][0]["price_rub"] == 100


def test_evaluate_for_day_returns_candidates_without_writes(monkeypatch) -> None:
    store = FakeStore()
    monkeypatch.setattr(engine_mod.fx_mod, "compute_features_for_day", lambda *_args, **_kwargs: {"x": 1.0})
    monkeypatch.setattr(engine_mod, "estimate_hazard", lambda _features: 0.1)
    monkeypatch.setattr(engine_mod, "estimate_readiness", lambda _features: 0.8)
    monkeypatch.setattr(engine_mod, "should_suppress_marketing", lambda **_kwargs: False)
    monkeypatch.setattr(engine_mod, "has_active_entitlement", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(engine_mod, "is_outbound_overloaded", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(engine_mod, "daily_offer_cap_reached", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(engine_mod, "build_candidates", lambda **_kwargs: ([('a', 1.0)], None))
    monkeypatch.setattr(engine_mod, "filter_candidate_arms", lambda *_args, candidates, **_kwargs: candidates)
    monkeypatch.setattr(
        engine_mod,
        "score_arm_candidates_event_sourced",
        lambda *_args, **_kwargs: [RetentionArmEvidence('a', 1, 2, 1, 2/3, 2/3, 1, 0, 'event_stream')],
    )
    monkeypatch.setattr(
        engine_mod,
        "build_price_candidates",
        lambda **_kwargs: [RetentionPriceEvidence(100, .2, 20, .5, True, True, {})],
    )
    result = engine_mod.evaluate_for_day(
        store,
        tenant_id="t",
        user_id="u",
        day_key="d",
        day_index=1,
        now_ms=100,
    )
    assert result.reason == "candidates_ready"
    assert len(result.candidates) == 1
    assert result.debug["no_second_brain"] is True
    assert store.feature_writes == 0 and store.ensure_calls == 0


def test_evaluate_suppression_and_no_candidate_paths(monkeypatch) -> None:
    store = FakeStore()
    monkeypatch.setattr(engine_mod.fx_mod, "compute_features_for_day", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(engine_mod, "estimate_hazard", lambda _features: 0.9)
    monkeypatch.setattr(engine_mod, "estimate_readiness", lambda _features: 0.1)
    monkeypatch.setattr(engine_mod, "should_suppress_marketing", lambda **_kwargs: True)
    suppressed = engine_mod.evaluate_for_day(
        store,
        tenant_id="t",
        user_id="u",
        day_key="d",
        day_index=1,
        now_ms=100,
    )
    assert suppressed.suppressed and suppressed.reason == "suppressed"

    monkeypatch.setattr(engine_mod, "estimate_hazard", lambda _features: 0.1)
    monkeypatch.setattr(engine_mod, "estimate_readiness", lambda _features: 0.8)
    monkeypatch.setattr(engine_mod, "should_suppress_marketing", lambda **_kwargs: False)
    monkeypatch.setattr(engine_mod, "has_active_entitlement", lambda *_args, **_kwargs: True)
    committed = engine_mod.evaluate_for_day(
        store,
        tenant_id="t",
        user_id="u",
        day_key="d",
        day_index=1,
        now_ms=100,
    )
    assert committed.reason == "committed"

    monkeypatch.setattr(engine_mod, "has_active_entitlement", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(engine_mod, "is_outbound_overloaded", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(engine_mod, "daily_offer_cap_reached", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(engine_mod, "build_candidates", lambda **_kwargs: ([], None))
    none = engine_mod.evaluate_for_day(
        store,
        tenant_id="t",
        user_id="u",
        day_key="d",
        day_index=1,
        now_ms=100,
    )
    assert not none.suppressed and none.reason == "no_candidates"


def test_materialization_requires_explicit_candidate() -> None:
    evidence = evaluation(candidate())
    neutral = neutral_decision(evidence)
    assert neutral.offer_arm == "NONE" and neutral.offer_price_rub is None
    selected = materialize_candidate(evidence, candidate_id="c1")
    assert selected.offer_arm == "offer_30_14900"
    assert selected.reason == "selected_by_decision_core"
    with pytest.raises(KeyError, match="unknown_retention_candidate"):
        materialize_candidate(evidence, candidate_id="missing")
