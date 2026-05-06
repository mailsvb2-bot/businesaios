from runtime.messaging_policy_events.inmemory_event_store import InMemoryMessagingPolicyEventStore
from runtime.messaging_policy_readmodel.boot_runtime import boot_messaging_policy_readmodel
from runtime.messaging_policy_readmodel.read_api import read_messaging_policy_snapshot


class _Runtime:
    pass


def test_bootstrap_attaches_read_services():
    runtime_obj = _Runtime()
    services = boot_messaging_policy_readmodel(runtime_obj=runtime_obj, event_store=InMemoryMessagingPolicyEventStore())
    assert hasattr(runtime_obj, 'messaging_policy_snapshot_store')
    assert hasattr(runtime_obj, 'messaging_policy_snapshot_repository')
    assert hasattr(runtime_obj, 'messaging_policy_read_service')
    out = read_messaging_policy_snapshot(
        read_service=runtime_obj.messaging_policy_read_service,
        tenant_id='t1',
        user_id='u1',
        correlation_id='c1',
    )
    assert out is None
    assert 'read_service' in services
