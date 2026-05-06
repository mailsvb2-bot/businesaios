from core.autopilot.read_model import recent_autopilot_actions, today_business_metrics


class _Store:
    def __init__(self, events):
        self._events = list(events)

    def iter_events(self, *, tenant_id, start_ms, event_type, end_ms=None):
        for ev in self._events:
            if str(ev.get("tenant_id") or "default") != str(tenant_id):
                continue
            if str(ev.get("event_type") or "") != str(event_type):
                continue
            ts = int(ev.get("timestamp_ms") or 0)
            if ts < int(start_ms):
                continue
            if end_ms is not None and ts >= int(end_ms):
                continue
            yield dict(ev)


def test_today_business_metrics_respects_now_ms_upper_bound():
    now_ms = 1_700_000_000_000
    start_ms = now_ms - 10_000
    store = _Store([
        {"tenant_id": "t", "event_type": "lead_created@v1", "timestamp_ms": start_ms + 1000, "user_id": "u1"},
        {"tenant_id": "t", "event_type": "lead_created@v1", "timestamp_ms": now_ms + 1000, "user_id": "u2"},
        {"tenant_id": "t", "event_type": "purchase_completed@v1", "timestamp_ms": start_ms + 2000, "user_id": "u1", "payload": {"amount_minor": 500}},
        {"tenant_id": "t", "event_type": "purchase_completed@v1", "timestamp_ms": now_ms + 2000, "user_id": "u2", "payload": {"amount_minor": 900}},
    ])

    got = today_business_metrics(store, tenant_id="t", now_ms=now_ms)
    assert got["leads"] == 1
    assert got["purchases"] == 1
    assert got["revenue_minor"] == 500


def test_recent_autopilot_actions_respects_now_ms_upper_bound():
    now_ms = 1_700_000_000_000
    store = _Store([
        {"tenant_id": "t", "event_type": "autopilot_decision@v1", "timestamp_ms": now_ms - 1000, "user_id": "u1", "payload": {"kind": "scale", "reason": "ok", "changes": {"a": 1}}},
        {"tenant_id": "t", "event_type": "autopilot_decision@v1", "timestamp_ms": now_ms + 1000, "user_id": "u2", "payload": {"kind": "future", "reason": "should_be_hidden"}},
    ])

    got = recent_autopilot_actions(store, tenant_id="t", now_ms=now_ms)
    assert len(got) == 1
    assert got[0]["kind"] == "scale"
