from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from core.pricing.rl_picker import RLPricingConfig, choose_price_rub


@dataclass
class _Ev:
    event_type: str
    tenant_id: str
    user_id: str
    timestamp_ms: int
    payload: dict[str, Any]


class _FakeStore:
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
        limit: int | None = None,
    ) -> Iterable[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for e in self._events:
            if str(e.tenant_id) != str(tenant_id):
                continue
            if int(e.timestamp_ms) < int(start_ms) or int(e.timestamp_ms) > int(end_ms):
                continue
            if user_id is not None and str(e.user_id) != str(user_id):
                continue
            if event_type is not None and str(e.event_type) != str(event_type):
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


def test_pricing_rl_disabled_returns_base() -> None:
    store = _FakeStore([])
    price, dbg = choose_price_rub(
        store,
        tenant_id="t1",
        offer_arm="offer_30_14900",
        base_price_rub=14900,
        cfg=RLPricingConfig(enabled=False),
        now_ms=1_000_000,
    )
    assert price == 14900
    assert dbg.get("note") == "disabled"


def test_pricing_rl_no_trials_returns_base() -> None:
    store = _FakeStore([])
    price, dbg = choose_price_rub(
        store,
        tenant_id="t1",
        offer_arm="offer_30_14900",
        base_price_rub=14900,
        cfg=RLPricingConfig(enabled=True, lookback_days=1),
        now_ms=1_000_000,
    )
    assert price == 14900
    assert dbg.get("note") == "no_trials"


def test_pricing_rl_prefers_higher_expected_revenue_when_data_supports() -> None:
    # Two price points: 14000 has lower conversion, 16000 has higher conversion.
    now_ms = 2_000_000
    t0 = now_ms - 10_000

    events: list[_Ev] = []
    # 10 selections at 14000, 1 success
    for i in range(10):
        uid = f"u{i}"
        events.append(
            _Ev(
                event_type="tariff_selected",
                tenant_id="t1",
                user_id=uid,
                timestamp_ms=t0 + i,
                payload={"tariff": "offer_30_14900", "amount": 14000},
            )
        )
        if i == 0:
            events.append(
                _Ev(
                    event_type="payment_captured",
                    tenant_id="t1",
                    user_id=uid,
                    timestamp_ms=t0 + i + 100,
                    payload={"amount": 14000, "ok": True},
                )
            )

    # 6 selections at 16000, 3 successes
    for i in range(6):
        uid = f"x{i}"
        events.append(
            _Ev(
                event_type="tariff_selected",
                tenant_id="t1",
                user_id=uid,
                timestamp_ms=t0 + 500 + i,
                payload={"tariff": "offer_30_14900", "amount": 16000},
            )
        )
        if i < 3:
            events.append(
                _Ev(
                    event_type="payment_captured",
                    tenant_id="t1",
                    user_id=uid,
                    timestamp_ms=t0 + 500 + i + 100,
                    payload={"amount": 16000, "ok": True},
                )
            )

    store = _FakeStore(events)

    cfg = RLPricingConfig(
        enabled=True,
        lookback_days=7,
        window_hours=24,
        grid_radius_pct=0.20,
        grid_step_rub=1000,
        min_price_rub=1000,
        max_price_rub=100000,
        prior_alpha=1.0,
        prior_beta=1.0,
        seed_salt="test",
    )

    picked, dbg = choose_price_rub(
        store,
        tenant_id="t1",
        offer_arm="offer_30_14900",
        base_price_rub=15000,
        cfg=cfg,
        now_ms=now_ms,
    )

    # With the given evidence and relatively weak priors, 16000 should be competitive.
    assert int(picked) in {15000, 16000}
    assert dbg.get("note") == "ok"
    assert dbg.get("trials", 0) >= 16


def test_pricing_rl_context_key_segments_trials() -> None:
    now_ms = 3_000_000
    t0 = now_ms - 10_000

    events: list[_Ev] = []

    # Segment A: 16000 converts well.
    for i in range(10):
        uid = f"a{i}"
        events.append(
            _Ev(
                event_type="tariff_selected",
                tenant_id="t1",
                user_id=uid,
                timestamp_ms=t0 + i,
                payload={"tariff": "offer_30_14900", "amount": 16000, "traffic_source": "A"},
            )
        )
        if i < 5:
            events.append(
                _Ev(
                    event_type="payment_captured",
                    tenant_id="t1",
                    user_id=uid,
                    timestamp_ms=t0 + i + 100,
                    payload={"amount": 16000, "ok": True},
                )
            )

    # Segment B: 14000 converts well.
    for i in range(10):
        uid = f"b{i}"
        events.append(
            _Ev(
                event_type="tariff_selected",
                tenant_id="t1",
                user_id=uid,
                timestamp_ms=t0 + 500 + i,
                payload={"tariff": "offer_30_14900", "amount": 14000, "traffic_source": "B"},
            )
        )
        if i < 5:
            events.append(
                _Ev(
                    event_type="payment_captured",
                    tenant_id="t1",
                    user_id=uid,
                    timestamp_ms=t0 + 500 + i + 100,
                    payload={"amount": 14000, "ok": True},
                )
            )

    store = _FakeStore(events)
    cfg = RLPricingConfig(
        enabled=True,
        lookback_days=7,
        window_hours=24,
        grid_radius_pct=0.30,
        grid_step_rub=1000,
        min_price_rub=1000,
        max_price_rub=100000,
        prior_alpha=1.0,
        prior_beta=1.0,
        seed_salt="test_ctx",
    )

    p_a, dbg_a = choose_price_rub(
        store,
        tenant_id="t1",
        offer_arm="offer_30_14900",
        base_price_rub=15000,
        cfg=cfg,
        now_ms=now_ms,
        context_key="A",
    )
    p_b, dbg_b = choose_price_rub(
        store,
        tenant_id="t1",
        offer_arm="offer_30_14900",
        base_price_rub=15000,
        cfg=cfg,
        now_ms=now_ms,
        context_key="B",
    )

    assert dbg_a.get("context_key") == "A"
    assert dbg_b.get("context_key") == "B"
    assert int(p_a) in {15000, 16000}
    assert int(p_b) in {15000, 14000}
