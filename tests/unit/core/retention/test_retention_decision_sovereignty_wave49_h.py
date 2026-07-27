from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import core.retention.arms as arms_mod
import core.policies.telegram.unified_policy as unified_mod
from core.policies.telegram.helpers import propose
from core.retention.decision_adapter import RetentionDecisionAdapter
from core.retention.engine import RetentionEvaluation, RetentionOfferCandidate
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


def test_adapter_remaining_candidate_and_context_branches(monkeypatch) -> None:
    adapter = RetentionDecisionAdapter(
        event_store=FakeStore(),
        tenant_id="tenant-a",
        prices={"p30": 100},
        offer_engine=FakeOfferEngine(),
    )
    assert adapter._outbound() is None
    evidence = evaluation(candidate("one"), candidate("two"))
    monkeypatch.setattr(
        __import__("core.retention.decision_adapter", fromlist=["x"]),
        "build_offer_proposal",
        lambda **kwargs: None if kwargs["candidate"].candidate_id == "one" else propose("noop@v1", {}),
    )
    result = adapter.propose_candidates(
        state=FakeState(user_id=None),
        base=propose("noop@v1", {"user_id": "fallback"}),
        evaluation=evidence,
    )
    assert len(result) == 2

    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        adapter._engine,
        "decide_offer",
        lambda **kwargs: captured.update(kwargs) or None,
    )
    adapter.maybe_decide_offer(
        tenant_id="tenant-a",
        user_id="u",
        context={"prices": {"p30": 5}, "outbound_telemetry": {}},
    )
    assert captured["context"]["prices"] == {"p30": 5}


def test_unified_retention_domain_direct_and_empty_pricing_key(monkeypatch) -> None:
    monkeypatch.setattr(unified_mod, "handle", lambda *_args, **_kwargs: propose("noop@v1", {}))

    class Domain:
        def propose(self, _state):
            return propose("noop@v1", {"domain": "retention"})

    policy = unified_mod.UnifiedTelegramPolicyV3()
    policy._ret = Domain()
    state = FakeState(product={"domain": "retention"})
    assert policy.propose(state).payload["domain"] == "retention"
    assert policy.propose_many(state)[0].payload["domain"] == "retention"

    normal = unified_mod.UnifiedTelegramPolicyV3()
    context, _ = normal._context(
        FakeState(user={"pricing_suggestions": {"": 1, "ok": 2}})
    )
    assert context.pricing_suggestions == {"ok": 2}


def test_tracking_remaining_warning_and_nonlist_paths() -> None:
    from runtime._internal.effects_actions.telegram.messaging_parts.tracking import emit_warning

    class AlwaysFail:
        def emit(self, **_kwargs: Any) -> None:
            raise RuntimeError

    emit_warning(
        AlwaysFail(),
        user_id="u",
        decision_id="d",
        correlation_id="c",
        reason="x",
    )
    owner = SimpleNamespace(event_log=SimpleNamespace(events=[]))
    owner.event_log.emit = lambda **kwargs: owner.event_log.events.append(kwargs)
    track_business_event(
        owner,
        user_id="u",
        decision_id="d",
        correlation_id="c",
        track_event_type="x",
        track_payload={"additional_track_events": "not-list"},
    )
    assert len(owner.event_log.events) == 1


def test_last_branch_arcs() -> None:
    now = 10_000
    no_day_index = FakeStore(
        [
            {
                "event_type": "offer_shown",
                "payload": {"arm": "offer_30_14900"},
                "timestamp_ms": now - 1,
            }
        ]
    )
    assert arms_mod.arm_already_shown_in_window(
        no_day_index,
        tenant_id="t",
        user_id="u",
        arm="offer_30_14900",
        window_day_from=1,
        window_day_to=2,
        now_ms=now,
    )
    zero_then_other = FakeStore(
        [
            {
                "event_type": "offer_shown",
                "payload": {"arm": "offer_30_14900"},
                "timestamp_ms": 0,
            },
            {"event_type": "other"},
        ]
    )
    assert not arms_mod.arm_already_shown_in_window(
        zero_then_other,
        tenant_id="t",
        user_id="u",
        arm="offer_30_14900",
        window_day_from=1,
        window_day_to=2,
        now_ms=now,
    )
    adapter = RetentionDecisionAdapter(
        event_store=FakeStore(),
        tenant_id="tenant-a",
        logger=None,
        offer_engine=FakeOfferEngine(),
    )
    adapter._engine.decide_offer = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError())
    assert adapter.maybe_decide_offer(tenant_id="t", user_id="u", context={}) is None
