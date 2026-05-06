from runtime.messaging_policy_readmodel.inmemory_store import InMemoryMessagingPolicySnapshotStore
from runtime.messaging_policy_readmodel.repository import MessagingPolicySnapshotRepository
from runtime.messaging_policy_readmodel.snapshot_record import MessagingPolicySnapshotRecord


def test_repository_put_and_get():
    repo = MessagingPolicySnapshotRepository(store=InMemoryMessagingPolicySnapshotStore())
    snap = MessagingPolicySnapshotRecord(
        tenant_id='t1',
        user_id='u1',
        correlation_id='c1',
        delivered=('sms',),
        failed=('telegram',),
        blocked=(),
        last_plan_channels=('telegram', 'sms'),
        last_selected_channel='sms',
        last_terminal_reason='',
        attempts_count=2,
    )
    repo.put(snap)
    loaded = repo.get(tenant_id='t1', user_id='u1', correlation_id='c1')
    assert loaded is not None
    assert loaded.last_selected_channel == 'sms'
