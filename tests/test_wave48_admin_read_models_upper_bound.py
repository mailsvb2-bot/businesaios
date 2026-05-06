from __future__ import annotations

from core.admin.read_models.pricing import pricing_change_requests
from core.admin.read_models.retention import health_brief, retention_brief
from core.admin.read_models.traffic import (
    ab_offers_summary,
    demo_summary,
    funnel2_report,
    giftshare_summary,
    segments_summary,
    users_today,
)


class _Store:
    def __init__(self, events):
        self._events = list(events)

    def iter_events(self, *, tenant_id, start_ms=0, end_ms=None, event_type=None):
        for ev in self._events:
            if str(ev.get("tenant_id", "default")) != str(tenant_id):
                continue
            ts = int(ev.get("timestamp_ms") or 0)
            if ts < int(start_ms):
                continue
            if end_ms is not None and ts > int(end_ms):
                continue
            if event_type is not None and str(ev.get("event_type") or "") != str(event_type):
                continue
            yield ev


def _event(event_type: str, ts: int, user_id: str = "u1", payload=None):
    return {
        "tenant_id": "default",
        "event_type": event_type,
        "timestamp_ms": int(ts),
        "user_id": user_id,
        "payload": payload or {},
    }


def test_pricing_change_requests_respects_upper_bound() -> None:
    now_ms = 1_000
    store = _Store(
        [
            _event("pricing_change_requested", 900, payload={"request_id": "r1", "plan_id": 1, "new_price": 100}),
            _event("pricing_change_applied", 950, payload={"request_id": "r1"}),
            _event("pricing_change_requested", 1_100, payload={"request_id": "future", "plan_id": 2, "new_price": 200}),
        ]
    )
    rows = pricing_change_requests(store, now_ms=now_ms)
    assert [row["request_id"] for row in rows] == ["r1"]
    assert rows[0]["status"] == "applied"


def test_retention_read_models_respect_upper_bound() -> None:
    now_ms = 5_000
    store = _Store(
        [
            _event("lead_created@v1", 1_000, user_id="u1"),
            _event("purchase_completed@v1", 2_000, user_id="u1"),
            _event("gift_sent", 9_000, user_id="future"),
        ]
    )
    brief = retention_brief(store, days=30, now_ms=now_ms)
    health = health_brief(store, now_ms=now_ms)
    assert brief["users"] == 1
    assert health["events"] == 2


def test_traffic_read_models_respect_upper_bound() -> None:
    now_ms = 10_000
    store = _Store(
        [
            _event("audio_sent", 1_000, user_id="u1", payload={"path": "work/demo.mp3"}),
            _event("payment_captured", 2_000, user_id="u1"),
            _event("access_granted", 3_000, user_id="u1"),
            _event("marketing_copy_set", 4_000, user_id="u1"),
            _event("share_clicked", 5_000, user_id="u1"),
            _event("tariffs_viewed", 6_000, user_id="u1"),
            _event("tariff_selected", 7_000, user_id="u1"),
            _event("payment_created", 8_000, user_id="u1"),
            _event("audio_sent", 20_000, user_id="future", payload={"path": "home/demo.mp3"}),
            _event("marketing_copy_chosen", 21_000, user_id="future"),
            _event("gift_sent", 22_000, user_id="future"),
            _event("payment_captured", 23_000, user_id="future"),
        ]
    )

    assert users_today(store, now_ms=now_ms) == 1
    assert demo_summary(store, now_ms=now_ms)["users"] == 1
    assert segments_summary(store, now_ms=now_ms)["payers_30d"] == 1
    assert ab_offers_summary(store, now_ms=now_ms)["variants_chosen"] == 0
    assert giftshare_summary(store, now_ms=now_ms)["gift_sent"] == 0
    funnel = funnel2_report(store, now_ms=now_ms)
    assert funnel["counts"]["payment_captured"] == 1
