from runtime.messaging_policy_events.event_factory import build_event
from runtime.messaging_policy_trace.summary_builder import MessagingPolicyTraceSummaryBuilder


def test_summary_builder_builds_trace_summary():
    builder = MessagingPolicyTraceSummaryBuilder()
    records = [
        build_event(tenant_id='t1', user_id='u1', decision_id='d1', correlation_id='c1', event_type='messaging_policy_plan_created', payload={'ordered_channels': ['telegram', 'sms']}, created_at='2026-03-01T10:00:00+00:00'),
        build_event(tenant_id='t1', user_id='u1', decision_id='d1', correlation_id='c1', event_type='messaging_message_failed', payload={'channel': 'telegram'}, created_at='2026-03-01T10:01:00+00:00'),
        build_event(tenant_id='t1', user_id='u1', decision_id='d1', correlation_id='c1', event_type='messaging_message_delivered', payload={'channel': 'sms'}, created_at='2026-03-01T10:02:00+00:00'),
        build_event(tenant_id='t1', user_id='u1', decision_id='d1', correlation_id='c1', event_type='messaging_policy_execution_finished', payload={'selected_channel': 'sms', 'terminal_reason': '', 'attempts_count': 2}, created_at='2026-03-01T10:03:00+00:00'),
    ]
    out = builder.build_one(records)
    assert out is not None
    assert out.selected_channel == 'sms'
    assert out.attempts_count == 2
    assert out.updated_at == '2026-03-01T10:03:00+00:00'
