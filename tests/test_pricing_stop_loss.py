from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from core.pricing.stop_loss import StopLossConfig, should_apply_price


@dataclass
class _Ev:
    event_type: str
    tenant_id: str
    user_id: str
    timestamp_ms: int
    payload: Dict[str, Any]


class _FakeStore:
    def __init__(self, events: List[_Ev]):
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
    ) -> Iterable[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
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


def test_stop_loss_blocks_candidate_on_conv_drop() -> None:
    now_ms = 10_000_000
    t0 = now_ms - 60_000

    events: List[_Ev] = []

    # Baseline 15000: 30 trials, 9 successes (30%)
    for i in range(30):
        uid = f"b{i}"
        events.append(
            _Ev(
                event_type="tariff_selected",
                tenant_id="t1",
                user_id=uid,
                timestamp_ms=t0 + i,
                payload={"tariff": "offer_30_14900", "amount": 15000, "traffic_source": "A"},
            )
        )
        if i < 9:
            events.append(
                _Ev(
                    event_type="payment_captured",
                    tenant_id="t1",
                    user_id=uid,
                    timestamp_ms=t0 + i + 100,
                    payload={"amount": 15000, "ok": True},
                )
            )

    # Candidate 17000: 30 trials, 3 successes (10%)
    for i in range(30):
        uid = f"c{i}"
        events.append(
            _Ev(
                event_type="tariff_selected",
                tenant_id="t1",
                user_id=uid,
                timestamp_ms=t0 + 500 + i,
                payload={"tariff": "offer_30_14900", "amount": 17000, "traffic_source": "A"},
            )
        )
        if i < 3:
            events.append(
                _Ev(
                    event_type="payment_captured",
                    tenant_id="t1",
                    user_id=uid,
                    timestamp_ms=t0 + 500 + i + 100,
                    payload={"amount": 17000, "ok": True},
                )
            )

    store = _FakeStore(events)
    cfg = StopLossConfig(enabled=True, lookback_hours=24, min_trials=20, max_conv_drop_pct=0.20, max_rev_drop_pct=0.50)

    ok, dbg = should_apply_price(
        store,
        tenant_id="t1",
        offer_arm="offer_30_14900",
        candidate_price_rub=17000,
        base_price_rub=15000,
        cfg=cfg,
        now_ms=now_ms,
        context_key="A",
        window_hours=24,
    )

    assert ok is False
    assert dbg.get("note") in {"blocked_conv_drop", "blocked_rev_drop"}


def test_stop_loss_allows_when_insufficient_trials() -> None:
    now_ms = 11_000_000
    t0 = now_ms - 60_000

    events: List[_Ev] = []
    # Baseline has enough trials
    for i in range(30):
        uid = f"b{i}"
        events.append(
            _Ev(
                event_type="tariff_selected",
                tenant_id="t1",
                user_id=uid,
                timestamp_ms=t0 + i,
                payload={"tariff": "offer_30_14900", "amount": 15000},
            )
        )
        if i < 6:
            events.append(
                _Ev(
                    event_type="payment_captured",
                    tenant_id="t1",
                    user_id=uid,
                    timestamp_ms=t0 + i + 100,
                    payload={"amount": 15000, "ok": True},
                )
            )

    # Candidate has too few trials
    for i in range(5):
        uid = f"c{i}"
        events.append(
            _Ev(
                event_type="tariff_selected",
                tenant_id="t1",
                user_id=uid,
                timestamp_ms=t0 + 500 + i,
                payload={"tariff": "offer_30_14900", "amount": 17000},
            )
        )

    store = _FakeStore(events)
    cfg = StopLossConfig(enabled=True, lookback_hours=24, min_trials=20)

    ok, dbg = should_apply_price(
        store,
        tenant_id="t1",
        offer_arm="offer_30_14900",
        candidate_price_rub=17000,
        base_price_rub=15000,
        cfg=cfg,
        now_ms=now_ms,
        window_hours=24,
    )

    assert ok is True
    assert dbg.get("note") == "insufficient_trials"


def test_stop_loss_cooldown_blocks_even_without_recomputing() -> None:
    now_ms = 12_000_000
    t0 = now_ms - 60_000

    events: List[_Ev] = []

    # A recent stop-loss trigger event for this offer+segment should activate cooldown.
    events.append(
        _Ev(
            event_type="pricing_stoploss_triggered",
            tenant_id="t1",
            user_id="u1",
            timestamp_ms=now_ms - 10_000,
            payload={"offer_arm": "offer_30_14900", "segment": "A", "reason": "blocked_conv_drop"},
        )
    )

    # Add some normal trials (should not matter due to cooldown)
    for i in range(30):
        uid = f"b{i}"
        events.append(
            _Ev(
                event_type="tariff_selected",
                tenant_id="t1",
                user_id=uid,
                timestamp_ms=t0 + i,
                payload={"tariff": "offer_30_14900", "amount": 15000, "traffic_source": "A"},
            )
        )

    store = _FakeStore(events)
    cfg = StopLossConfig(enabled=True, lookback_hours=24, min_trials=20, cooldown_hours=6)

    ok, dbg = should_apply_price(
        store,
        tenant_id="t1",
        offer_arm="offer_30_14900",
        candidate_price_rub=17000,
        base_price_rub=15000,
        cfg=cfg,
        now_ms=now_ms,
        context_key="A",
        window_hours=24,
    )

    assert ok is False
    assert dbg.get("note") == "cooldown_active"
    assert dbg.get("cooldown_effective_hours") == 6
    assert dbg.get("cooldown_recent_triggers") == 1


def test_stop_loss_cooldown_backoff_increases_window() -> None:
    now_ms = 1_700_000_000_000
    base_h = 6

    # Two triggers in horizon -> effective cooldown = 12h.
    events: List[_Ev] = [
        _Ev(
            event_type="pricing_stoploss_triggered",
            tenant_id="t1",
            user_id="u1",
            timestamp_ms=now_ms - int(10 * 3600 * 1000),
            payload={"offer_arm": "offer_30_14900", "segment": "A", "reason": "blocked_conv_drop"},
        ),
        _Ev(
            event_type="pricing_stoploss_triggered",
            tenant_id="t1",
            user_id="u1",
            timestamp_ms=now_ms - int(8 * 3600 * 1000),
            payload={"offer_arm": "offer_30_14900", "segment": "A", "reason": "blocked_rev_drop"},
        ),
    ]

    store = _FakeStore(events)
    cfg = StopLossConfig(enabled=True, cooldown_hours=base_h, cooldown_max_hours=24, cooldown_backoff_lookback_hours=72)

    ok, dbg = should_apply_price(
        store,
        tenant_id="t1",
        offer_arm="offer_30_14900",
        candidate_price_rub=17000,
        base_price_rub=15000,
        cfg=cfg,
        now_ms=now_ms,
        context_key="A",
        window_hours=24,
    )

    assert ok is False
    assert dbg.get("note") == "cooldown_active"
    assert dbg.get("cooldown_effective_hours") == 12
    assert dbg.get("cooldown_recent_triggers") == 2


def test_stop_loss_cooldown_backoff_caps_at_max() -> None:
    now_ms = 1_700_000_100_000
    base_h = 6

    # Three triggers -> 24h effective (6 * 2^(3-1) = 24), capped at 24.
    events: List[_Ev] = [
        _Ev(
            event_type="pricing_stoploss_triggered",
            tenant_id="t1",
            user_id="u1",
            timestamp_ms=now_ms - int(60 * 3600 * 1000),
            payload={"offer_arm": "offer_30_14900", "segment": "A", "reason": "blocked_conv_drop"},
        ),
        _Ev(
            event_type="pricing_stoploss_triggered",
            tenant_id="t1",
            user_id="u1",
            timestamp_ms=now_ms - int(40 * 3600 * 1000),
            payload={"offer_arm": "offer_30_14900", "segment": "A", "reason": "blocked_rev_drop"},
        ),
        _Ev(
            event_type="pricing_stoploss_triggered",
            tenant_id="t1",
            user_id="u1",
            timestamp_ms=now_ms - int(20 * 3600 * 1000),
            payload={"offer_arm": "offer_30_14900", "segment": "A", "reason": "blocked_rev_drop"},
        ),
    ]

    store = _FakeStore(events)
    cfg = StopLossConfig(enabled=True, cooldown_hours=base_h, cooldown_max_hours=24, cooldown_backoff_lookback_hours=72)

    ok, dbg = should_apply_price(
        store,
        tenant_id="t1",
        offer_arm="offer_30_14900",
        candidate_price_rub=17000,
        base_price_rub=15000,
        cfg=cfg,
        now_ms=now_ms,
        context_key="A",
        window_hours=24,
    )

    assert ok is False
    assert dbg.get("note") == "cooldown_active"
    assert dbg.get("cooldown_effective_hours") == 24
    assert dbg.get("cooldown_recent_triggers") == 3
