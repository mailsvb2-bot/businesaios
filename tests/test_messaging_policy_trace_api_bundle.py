from runtime.messaging_policy_events.event_factory import build_event
from runtime.messaging_policy_events.inmemory_event_store import InMemoryMessagingPolicyEventStore
from runtime.boot.web.runtime_web_service_builders import build_messaging_policy_trace_search_bundle


def test_trace_search_bundle_returns_items():
    event_store = InMemoryMessagingPolicyEventStore()
    event_store.append(build_event(tenant_id='t1', user_id='u1', decision_id='d1', correlation_id='c1', event_type='messaging_policy_plan_created', payload={'ordered_channels': ['telegram', 'email']}, created_at='2026-03-01T10:00:00+00:00'))
    event_store.append(build_event(tenant_id='t1', user_id='u1', decision_id='d1', correlation_id='c1', event_type='messaging_message_delivered', payload={'channel': 'email'}, created_at='2026-03-01T10:01:00+00:00'))
    event_store.append(build_event(tenant_id='t1', user_id='u1', decision_id='d1', correlation_id='c1', event_type='messaging_policy_execution_finished', payload={'selected_channel': 'email', 'terminal_reason': '', 'attempts_count': 1}, created_at='2026-03-01T10:02:00+00:00'))
    bundle = build_messaging_policy_trace_search_bundle(event_store=event_store)
    out = bundle.json(tenant_id='t1', user_id='u1', date_from='', date_to='', limit=50)
    assert out.status_code == 200
    assert out.body['count'] == 1
    assert out.body['items'][0]['selected_channel'] == 'email'
