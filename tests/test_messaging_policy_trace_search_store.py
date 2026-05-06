from runtime.messaging_policy_events.event_factory import build_event
from runtime.messaging_policy_events.inmemory_event_store import InMemoryMessagingPolicyEventStore
from runtime.messaging_policy_trace.search_store import MessagingPolicyTraceSearchStore


def test_search_store_filters_by_tenant_user_and_date():
    store = InMemoryMessagingPolicyEventStore()
    store.append(build_event(tenant_id='t1', user_id='u1', decision_id='d1', correlation_id='c1', event_type='messaging_message_delivered', payload={'channel': 'sms'}, created_at='2026-03-01T10:00:00+00:00'))
    store.append(build_event(tenant_id='t1', user_id='u2', decision_id='d2', correlation_id='c2', event_type='messaging_message_failed', payload={'channel': 'telegram'}, created_at='2026-03-02T10:00:00+00:00'))
    search = MessagingPolicyTraceSearchStore(event_store=store)
    out = search.search_records(tenant_id='t1', user_id='u1', date_from='2026-03-01T00:00:00+00:00', date_to='2026-03-01T23:59:59+00:00')
    assert len(out) == 1
    assert out[0].user_id == 'u1'
