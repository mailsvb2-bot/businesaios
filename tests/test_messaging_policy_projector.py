from runtime.messaging_policy_events.event_factory import build_event
from runtime.messaging_policy_readmodel.projector import MessagingPolicyProjector


def test_projector_builds_snapshot_from_records():
    projector = MessagingPolicyProjector()
    records = [
        build_event(
            tenant_id='t1',
            user_id='u1',
            decision_id='d1',
            correlation_id='c1',
            event_type='messaging_policy_plan_created',
            payload={'ordered_channels': ['telegram', 'whatsapp', 'sms']},
        ),
        build_event(
            tenant_id='t1',
            user_id='u1',
            decision_id='d1',
            correlation_id='c1',
            event_type='messaging_message_failed',
            payload={'channel': 'telegram'},
        ),
        build_event(
            tenant_id='t1',
            user_id='u1',
            decision_id='d1',
            correlation_id='c1',
            event_type='messaging_message_delivered',
            payload={'channel': 'whatsapp'},
        ),
        build_event(
            tenant_id='t1',
            user_id='u1',
            decision_id='d1',
            correlation_id='c1',
            event_type='messaging_policy_execution_finished',
            payload={'selected_channel': 'whatsapp', 'terminal_reason': '', 'attempts_count': 2},
        ),
    ]
    snap = projector.project(records)
    assert snap.delivered == ('whatsapp',)
    assert snap.failed == ('telegram',)
    assert snap.last_plan_channels == ('telegram', 'whatsapp', 'sms')
    assert snap.last_selected_channel == 'whatsapp'
    assert snap.attempts_count == 2
