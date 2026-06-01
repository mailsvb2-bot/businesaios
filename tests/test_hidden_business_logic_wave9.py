from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from config.pricing_retention_policy import (
    PricingOffPolicyDefaults,
    PricingStopLossPolicy,
    RetentionEnginePolicy,
)
from config.retention_arms_policy import RetentionArmsPolicy
from core.pricing.off_policy import ips_estimate_for_price
from core.pricing.stop_loss import StopLossConfig, should_apply_price
from core.retention import engine as engine_mod
from core.retention.arms import choose_arm_event_sourced
from core.retention.engine import RetentionDayDecision, RetentionEngine
from core.retention.engine_support import (
    build_sandbox_suppressed_decision,
    is_outbound_overloaded,
)


@dataclass
class _Ev:
    event_type: str
    tenant_id: str
    user_id: str
    timestamp_ms: int
    payload: dict[str, Any]


class _PricingStore:
    def __init__(self, events: list[_Ev]):
        self._events = list(events)

    def iter_events(
        self,
        *,
        tenant_id: str,
        start_ms: int,
        end_ms: int,
        user_id: str | None = None,
        event_type: str | None = None,
        event_types: tuple[str, ...] | None = None,
        limit: int | None = None,
    ) -> Iterable[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for e in self._events:
            if e.tenant_id != tenant_id:
                continue
            if e.timestamp_ms < start_ms or e.timestamp_ms > end_ms:
                continue
            if user_id is not None and e.user_id != user_id:
                continue
            if event_type is not None and e.event_type != event_type:
                continue
            if event_types is not None and e.event_type not in event_types:
                continue
            out.append(
                {
                    "event_type": e.event_type,
                    "tenant_id": e.tenant_id,
                    "user_id": e.user_id,
                    "timestamp_ms": e.timestamp_ms,
                    "payload": dict(e.payload),
                }
            )
        return out[: int(limit) if limit else None]

    def latest_events(self, *, tenant_id: str, event_types: tuple[str, ...], limit: int) -> list[dict[str, Any]]:
        items = [
            {
                "event_type": e.event_type,
                "tenant_id": e.tenant_id,
                "user_id": e.user_id,
                "timestamp_ms": e.timestamp_ms,
                "payload": dict(e.payload),
            }
            for e in self._events
            if e.tenant_id == tenant_id and e.event_type in event_types
        ]
        items.sort(key=lambda x: x["timestamp_ms"], reverse=True)
        return items[:limit]


class _RetentionStore:
    def __init__(self):
        self._events: list[dict[str, Any]] = []

    def iter_events(self, *, tenant_id: str, start_ms: int, end_ms: int, user_id: str | None = None):
        return []

    def latest_events(self, *, tenant_id: str, user_id: str, event_type: str, limit: int):
        return []

    def bandit_ensure_arm(self, *, tenant_id: str, arm: str, now_ms: int) -> None:
        return None

    def bandit_get_arm(self, *, tenant_id: str, arm: str) -> tuple[int, int]:
        return (1, 1)


class _UnknownTenantStore:
    def iter_events(self, *, tenant_id, start_ms=0, end_ms=None, event_type=None):
        return iter([])


def test_ips_estimate_uses_policy_defaults_for_inverse_propensity() -> None:
    store = _PricingStore(
        [
            _Ev(
                event_type="pricing_action_logged@v1",
                tenant_id="t1",
                user_id="u1",
                timestamp_ms=10,
                payload={
                    "offer_arm": "offer_30_14900",
                    "price_rub": 14900,
                    "propensity": 0.5,
                    "reward_minor": 100.0,
                },
            )
        ]
    )
    estimate = ips_estimate_for_price(
        store,
        tenant_id="t1",
        offer_arm="offer_30_14900",
        target_price_rub=14900,
        start_ms=0,
        end_ms=100,
        policy=PricingOffPolicyDefaults(inverse_propensity_numerator=2.0),
    )
    assert estimate.n == 1
    assert estimate.estimate_reward_minor == 100.0
    assert estimate.effective_n == 4.0


def test_stop_loss_uses_policy_unit_ratio() -> None:
    now_ms = 10_000_000
    t0 = now_ms - 60_000
    events: list[_Ev] = []
    for i in range(30):
        uid = f"b{i}"
        events.append(_Ev("tariff_selected", "t1", uid, t0 + i, {"tariff": "offer_30_14900", "amount": 15000}))
        if i < 9:
            events.append(_Ev("payment_captured", "t1", uid, t0 + i + 100, {"amount": 15000, "ok": True}))
    for i in range(30):
        uid = f"c{i}"
        events.append(_Ev("tariff_selected", "t1", uid, t0 + 500 + i, {"tariff": "offer_30_14900", "amount": 17000}))
        if i < 9:
            events.append(_Ev("payment_captured", "t1", uid, t0 + 500 + i + 100, {"amount": 17000, "ok": True}))
    ok, dbg = should_apply_price(
        _PricingStore(events),
        tenant_id="t1",
        offer_arm="offer_30_14900",
        candidate_price_rub=17000,
        base_price_rub=15000,
        cfg=StopLossConfig(enabled=True, lookback_hours=24, min_trials=20, max_conv_drop_pct=0.2, max_rev_drop_pct=0.2),
        now_ms=now_ms,
        window_hours=24,
        policy=PricingStopLossPolicy(unit_ratio=2.0),
    )
    assert ok is False
    assert dbg["note"] == "blocked_conv_drop"


def test_choose_arm_event_sourced_uses_policy_fallback_arm() -> None:
    arm = choose_arm_event_sourced(
        _RetentionStore(),
        tenant_id="t1",
        user_id="u1",
        arms=[],
        now_ms=1,
        policy=RetentionArmsPolicy(fallback_arm="offer_bundle_14_30"),
    )
    assert arm == "offer_bundle_14_30"


def test_retention_support_uses_policy_thresholds() -> None:
    assert is_outbound_overloaded(
        {"queue_size": 10, "wait_p90_ms": 50},
        policy=RetentionEnginePolicy(outbound_queue_size_threshold=5),
    ) is True
    sandbox = build_sandbox_suppressed_decision(
        tenant_id="t1",
        day_key="day:today",
        day_index=0,
        policy=RetentionEnginePolicy(sandbox_hazard=0.25, sandbox_readiness=0.75),
    )
    assert sandbox["hazard"] == 0.25
    assert sandbox["readiness"] == 0.75


def test_retention_engine_uses_policy_score_complement_base(monkeypatch) -> None:
    def _fake_decide_for_day(*args, **kwargs):
        return RetentionDayDecision(
            tenant_id="t1",
            day_key="day:today",
            day_index=0,
            hazard=0.25,
            readiness=0.5,
            offer_arm="offer_30_14900",
            offer_price_rub=14900,
            suppressed=False,
            reason="chosen",
            debug={},
        )

    monkeypatch.setattr(engine_mod, "decide_for_day", _fake_decide_for_day)
    monkeypatch.setattr(engine_mod, "is_retention_allowed", lambda **kwargs: True)
    engine = RetentionEngine(_UnknownTenantStore(), tenant_id="t1", policy=RetentionEnginePolicy(score_complement_base=2.0))
    decision = engine.decide_offer(tenant_id="t1", user_id="u1", context={})
    assert decision is not None
    assert decision.score == 0.875
