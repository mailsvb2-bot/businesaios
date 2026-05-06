from __future__ import annotations

from runtime.admin_state_support import send_optional_notification
from core.admin.read_models.latency import latency_brief, latency_breakdown, sla_breaches_brief
from core.admin.read_models.retention import retention_brief


class _EventStore:
    def __init__(self, events):
        self.events = list(events)
        self.calls = []

    def iter_events(self, **kwargs):
        self.calls.append(dict(kwargs))
        start_ms = kwargs.get("start_ms", 0)
        end_ms = kwargs.get("end_ms", 10**18)
        event_type = kwargs.get("event_type")
        for ev in self.events:
            if event_type and ev.get("event_type") != event_type:
                continue
            ts = int(ev.get("timestamp_ms") or 0)
            if ts < start_ms or ts > end_ms:
                continue
            yield ev


class _Owner:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = []

    def send_message(self, **kwargs):
        self.calls.append(dict(kwargs))
        if self.fail:
            raise RuntimeError("boom")
        return {"ok": True, "message_id": 1}


class _EventLog:
    def __init__(self):
        self.events = []

    def emit(self, **kwargs):
        self.events.append(dict(kwargs))


def test_latency_read_models_respect_explicit_now_ms_window():
    now_ms = 2_000_000
    inside_ts = now_ms - 1_000
    outside_ts = now_ms - 9 * 24 * 3600 * 1000
    store = _EventStore(
        [
            {"event_type": "latency_span", "timestamp_ms": inside_ts, "payload": {"stage": "router", "correlation_key": "c1", "extra": {"button_key": "go", "update_id": 1}}},
            {"event_type": "latency_span", "timestamp_ms": inside_ts, "payload": {"stage": "execute", "correlation_key": "c1", "duration_ms": 55, "extra": {"update_id": 1}}},
            {"event_type": "latency_span", "timestamp_ms": outside_ts, "payload": {"stage": "execute", "correlation_key": "old", "duration_ms": 999, "extra": {"update_id": 1}}},
            {"event_type": "latency_sla_breached", "timestamp_ms": inside_ts, "payload": {"ts_ms": inside_ts, "budget_ms": 100, "offenders": ["go"]}},
        ]
    )

    brief = latency_brief(store, days=7, now_ms=now_ms)
    breakdown = latency_breakdown(store, days=7, now_ms=now_ms)
    breaches = sla_breaches_brief(store, days=7, now_ms=now_ms)

    assert brief["samples"] == 1
    assert breakdown["samples"] == 1
    assert breaches["breaches"][0]["ts_ms"] == inside_ts
    assert all(call["end_ms"] == now_ms for call in store.calls if "end_ms" in call)


def test_retention_brief_respects_explicit_now_ms():
    now_ms = 10 * 24 * 3600 * 1000
    inside_a = now_ms - 1 * 24 * 3600 * 1000
    inside_b = now_ms - 2 * 24 * 3600 * 1000
    outside = now_ms - 40 * 24 * 3600 * 1000
    store = _EventStore(
        [
            {"timestamp_ms": inside_a, "user_id": "u1"},
            {"timestamp_ms": inside_b, "user_id": "u1"},
            {"timestamp_ms": outside, "user_id": "u2"},
        ]
    )
    brief = retention_brief(store, days=30, now_ms=now_ms)
    assert brief == {"users": 1, "active_2d": 1}


def test_admin_notification_event_emitted_only_after_success():
    owner = _Owner()
    log = _EventLog()
    result = send_optional_notification(
        owner,
        decision_id="d1",
        correlation_id="c1",
        admin_id="a1",
        notify_text="hello",
        notify_reply_markup=None,
        callback_query_id="cb1",
        channel="telegram",
        event_log=log,
    )
    assert result["ok"] is True
    assert [e["event_type"] for e in log.events] == ["admin_notification_sent"]


def test_admin_notification_failure_emits_failed_event_and_reraises():
    owner = _Owner(fail=True)
    log = _EventLog()
    try:
        send_optional_notification(
            owner,
            decision_id="d1",
            correlation_id="c1",
            admin_id="a1",
            notify_text="hello",
            notify_reply_markup=None,
            callback_query_id="cb1",
            channel="telegram",
            event_log=log,
        )
        raise AssertionError("expected RuntimeError")
    except RuntimeError:
        pass
    assert [e["event_type"] for e in log.events] == ["admin_notification_failed"]
