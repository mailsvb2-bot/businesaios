from runtime.messaging.outbound_message import OutboundMessage
from runtime.messaging_policy.policy_plan import PolicyPlan
from runtime.messaging_policy_events.event_recorder import MessagingPolicyEventRecorder
from runtime.messaging_policy_events.inmemory_event_store import InMemoryMessagingPolicyEventStore


def test_event_recorder_records_plan_attempt_and_finish():
    store = InMemoryMessagingPolicyEventStore()
    recorder = MessagingPolicyEventRecorder(store=store)

    msg = OutboundMessage(
        decision_id='d1',
        correlation_id='c1',
        tenant_id='t1',
        user_id='u1',
        channel='telegram',
        text='hello',
    )
    plan = PolicyPlan(
        ordered_channels=('whatsapp', 'sms'),
        reason_codes=('candidate_sequence_built',),
        terminal_reason='',
    )

    recorder.record_plan(msg=msg, plan=plan)
    recorder.record_attempt(msg=msg, ok=False, meta={'reason': 'blocked'})
    recorder.record_finished(
        msg=msg,
        plan=plan,
        selected_channel='',
        terminal_reason='all_attempts_failed',
        attempts_count=1,
    )

    items = store.read(tenant_id='t1', user_id='u1', correlation_id='c1')
    assert [item.event_type for item in items] == [
        'messaging_policy_plan_created',
        'messaging_message_attempted',
        'messaging_message_failed',
        'messaging_channel_blocked',
        'messaging_policy_execution_finished',
    ]
