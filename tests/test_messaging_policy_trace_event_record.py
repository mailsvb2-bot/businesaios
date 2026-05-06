from runtime.messaging_policy_events.event_factory import build_event


def test_build_event_sets_created_at():
    event = build_event(tenant_id='t1', user_id='u1', decision_id='d1', correlation_id='c1', event_type='messaging_message_attempted', payload={'channel': 'sms'})
    assert event.created_at
    assert event.tenant_id == 't1'
