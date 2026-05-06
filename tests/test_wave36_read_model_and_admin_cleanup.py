from __future__ import annotations

from core.autopilot.read_model import business_metrics_window, today_business_metrics
from core.policies.telegram.handlers.admin.pricing_support import back_markup, pending_rows


class _Store:
    def __init__(self, events):
        self._events = list(events)

    def iter_events(self, *, tenant_id, start_ms, event_type, end_ms=None):
        out = []
        for ev in self._events:
            if str(ev.get("tenant_id")) != str(tenant_id):
                continue
            if str(ev.get("event_type")) != str(event_type):
                continue
            ts = int(ev.get("timestamp_ms") or 0)
            if ts < int(start_ms):
                continue
            if end_ms is not None and ts >= int(end_ms):
                continue
            out.append(ev)
        return out


def test_business_metrics_window_respects_now_ms_and_day_boundaries():
    now_ms = 1740916800000  # 2025-03-02T00:00:00Z
    store = _Store([
        {"tenant_id": "t", "event_type": "lead_created@v1", "user_id": "u1", "timestamp_ms": 1740830400000, "payload": {}},
        {"tenant_id": "t", "event_type": "purchase_completed@v1", "user_id": "u1", "timestamp_ms": 1740830500000, "payload": {"amount_minor": 1990}},
        {"tenant_id": "t", "event_type": "lead_created@v1", "user_id": "u2", "timestamp_ms": 1740916700000, "payload": {}},
    ])
    window = business_metrics_window(store, tenant_id="t", days=2, now_ms=now_ms)
    assert len(window) == 2
    assert window[0]["purchases"] == 1
    assert window[0]["revenue_minor"] == 1990
    assert window[1]["leads"] == 1


def test_today_business_metrics_accepts_explicit_now_ms():
    now_ms = 1740916800000  # 2025-03-02T00:00:00Z
    store = _Store([
        {"tenant_id": "t", "event_type": "payment_succeeded", "user_id": "u9", "timestamp_ms": 1740916700000, "payload": {"amount": 500}},
    ])
    metrics = today_business_metrics(store, tenant_id="t", now_ms=now_ms)
    assert metrics["purchases"] == 1
    assert metrics["revenue_minor"] == 500


def test_pricing_support_builders_are_canonical():
    assert back_markup("admin:pricing:menu")["inline_keyboard"][0][0]["callback_data"] == "admin:pricing:menu"
    rows = pending_rows(request_id="abcdef123456")
    assert rows[0][0]["callback_data"] == "admin:pricing:approve:abcdef123456"
    assert rows[0][1]["callback_data"] == "admin:pricing:reject:abcdef123456"
