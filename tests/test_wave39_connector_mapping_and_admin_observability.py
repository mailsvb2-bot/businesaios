from __future__ import annotations

from datetime import date

from core.policies.telegram.handlers.admin.pricing_support import (
    parse_ai_request_callback,
    parse_plan_callback_id,
    pending_requests_view,
)
from interfaces.ads.connector_mapping_support import parse_metric_day, parse_optional_budget
from runtime.admin_state_support import send_optional_notification


class _DummyOwner:
    def __init__(self) -> None:
        self.calls = []

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return {"ok": True, "sent": True}


class _DummyEventLog:
    def __init__(self) -> None:
        self.events = []

    def emit(self, **kwargs):
        self.events.append(kwargs)


def test_parse_metric_day_is_shared_and_deterministic():
    assert parse_metric_day(
        row={"segments.date": "2026-03-01"},
        candidate_keys=("day", "date", "segments.date"),
        connector_name="GoogleAdsConnector",
    ) == date(2026, 3, 1)


def test_parse_optional_budget_prefers_first_valid_value():
    assert parse_optional_budget(None, "oops", "12.5") == 12.5


def test_admin_pricing_support_parses_callbacks_and_builds_pending_view():
    assert parse_plan_callback_id("admin:pricing:edit:42", prefix="admin:pricing:edit:") == 42
    assert parse_ai_request_callback("admin:pricing:ai_request:7:2290") == (7, 2290)
    text, markup = pending_requests_view([
        {"status": "pending", "request_id": "abcdef123456", "plan_id": 7, "new_price": 2290, "requested_by": "u1"},
    ])
    assert "#7" in text
    assert markup["inline_keyboard"][0][0]["callback_data"].startswith("admin:pricing:approve:")


def test_admin_notification_emits_observability_event_when_sent():
    owner = _DummyOwner()
    event_log = _DummyEventLog()
    result = send_optional_notification(
        owner,
        decision_id="d1",
        correlation_id="c1",
        admin_id="a1",
        notify_text="hello",
        notify_reply_markup=None,
        callback_query_id="cb1",
        channel="telegram",
        event_log=event_log,
    )
    assert result["ok"] is True
    assert owner.calls and owner.calls[0]["text"] == "hello"
    assert event_log.events and event_log.events[0]["event_type"] == "admin_notification_sent"
