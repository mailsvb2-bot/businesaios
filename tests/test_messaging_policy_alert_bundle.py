from runtime.boot.web.runtime_web_service_builders import (
    build_messaging_policy_alerts_bundle,
    build_messaging_policy_dashboard_bundle,
    build_messaging_policy_trace_search_bundle,
)
from runtime.messaging_policy_events.event_factory import build_event
from runtime.messaging_policy_events.inmemory_event_store import InMemoryMessagingPolicyEventStore


def test_alert_bundle_returns_json():
    event_store = InMemoryMessagingPolicyEventStore()
    event_store.append(build_event(tenant_id="t1", user_id="u1", decision_id="d1", correlation_id="c1", event_type="messaging_policy_plan_created", payload={"ordered_channels": ["telegram", "sms"]}, created_at="2026-03-01T10:00:00+00:00"))
    event_store.append(build_event(tenant_id="t1", user_id="u1", decision_id="d1", correlation_id="c1", event_type="messaging_message_failed", payload={"channel": "telegram"}, created_at="2026-03-01T10:01:00+00:00"))
    event_store.append(build_event(tenant_id="t1", user_id="u1", decision_id="d1", correlation_id="c1", event_type="messaging_policy_execution_finished", payload={"selected_channel": "", "terminal_reason": "all_attempts_failed", "attempts_count": 1}, created_at="2026-03-01T10:02:00+00:00"))
    trace_bundle = build_messaging_policy_trace_search_bundle(event_store=event_store)
    dashboard_bundle = build_messaging_policy_dashboard_bundle(trace_search_service=trace_bundle.search_service)
    bundle = build_messaging_policy_alerts_bundle(dashboard_service=dashboard_bundle.dashboard_service)
    out = bundle.json(tenant_id="t1", user_id="", date_from="", date_to="", limit=500)
    assert out.status_code == 200
    assert out.body["ok"] is True
    assert "alerts" in out.body
