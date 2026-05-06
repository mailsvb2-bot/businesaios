from runtime.messaging.outbound_message import OutboundMessage
from runtime.messaging_policy.policy_plan import PolicyPlan
from runtime.messaging_policy_events.event_recorder import MessagingPolicyEventRecorder
from runtime.messaging_policy_events.execute_with_events import execute_policy_plan_with_events
from runtime.messaging_policy_events.inmemory_event_store import InMemoryMessagingPolicyEventStore
from runtime.messaging_policy_readmodel.read_service import MessagingPolicyReadService
from runtime.messaging_policy_readmodel.projector import MessagingPolicyProjector
from runtime.messaging_policy_readmodel.repository import MessagingPolicySnapshotRepository
from runtime.messaging_policy_readmodel.inmemory_store import InMemoryMessagingPolicySnapshotStore
from runtime.messaging_policy_readmodel.rebuild_service import MessagingPolicyRebuildService


def test_execute_policy_plan_with_events_records_history():
    store = InMemoryMessagingPolicyEventStore()
    recorder = MessagingPolicyEventRecorder(store=store)

    attempts = []

    def send_once(msg):
        attempts.append(msg.channel)
        if msg.channel == 'whatsapp':
            return False, {'provider': 'whatsapp'}
        return True, {'provider': 'sms', 'external_id': 'sms-1'}

    ok, meta = execute_policy_plan_with_events(
        plan=PolicyPlan(
            ordered_channels=('whatsapp', 'sms'),
            reason_codes=('candidate_sequence_built',),
            terminal_reason='',
        ),
        base_message=OutboundMessage(
            decision_id='d1',
            correlation_id='c1',
            tenant_id='t1',
            user_id='u1',
            channel='telegram',
            text='hello',
        ),
        send_once=send_once,
        recorder=recorder,
    )

    assert ok is True
    assert attempts == ['whatsapp', 'sms']
    assert meta['policy']['selected_channel'] == 'sms'

    read_service = MessagingPolicyReadService(
        repository=MessagingPolicySnapshotRepository(store=InMemoryMessagingPolicySnapshotStore()),
        rebuild_service=MessagingPolicyRebuildService(
            event_store=store,
            projector=MessagingPolicyProjector(),
            repository=MessagingPolicySnapshotRepository(store=InMemoryMessagingPolicySnapshotStore()),
        ),
    )
    rebuilt = read_service._rebuild_service.rebuild_one(tenant_id='t1', user_id='u1', correlation_id='c1')
    assert rebuilt.failed == ('whatsapp',)
    assert rebuilt.delivered == ('sms',)
    assert rebuilt.last_selected_channel == 'sms'
