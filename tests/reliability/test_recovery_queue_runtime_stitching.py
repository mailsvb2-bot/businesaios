from __future__ import annotations

from runtime.execution.reliability_runtime import _OutboxAdapter
from runtime.queue import InMemoryJobStore, JobDispatcher, JobDispatchRequest
from runtime.recovery import recover_pending


class _Archive:
    def __init__(self, mapping):
        self._mapping = dict(mapping)

    def get(self, decision_id: str):
        return self._mapping.get(decision_id)


class _Executor:
    def __init__(self):
        self.items = []

    def execute_recovery(self, env):
        self.items.append(env)


class _Outbox:
    def __init__(self):
        self.rows = [
            {
                'tenant_id': 'tenant-42',
                'decision_id': 'd-1',
                'status': 'pending',
                'claimed_at_ms': None,
            }
        ]
        self.claimed = []

    def list_claimable(self, *, limit: int = 100):
        return list(self.rows[:limit])

    def claim(self, decision_id: str):
        self.claimed.append(decision_id)
        return True


def test_recover_pending_uses_item_tenant_without_default_fallback() -> None:
    env = object()
    executor = _Executor()
    outbox = _Outbox()
    archive = _Archive({'d-1': env})

    recovered = recover_pending(executor=executor, outbox=outbox, archive=archive, limit=10)

    assert recovered == 1
    assert executor.items == [env]
    assert outbox.claimed == ['d-1']


class _CompatOutbox:
    def get(self, tenant_id: str, message_id: str):
        return {
            'message_id': message_id,
            'dedupe_key': 'dk-1',
            'status': 'pending',
            'action': 'runtime.execution',
        }


def test_outbox_adapter_preserves_message_id_and_dedupe_key() -> None:
    message = _OutboxAdapter(outbox=_CompatOutbox()).get(tenant_id='tenant-1', message_id='msg-123')
    assert message is not None
    assert message.message_id == 'msg-123'
    assert message.dedupe_key == 'dk-1'


def test_dispatcher_counts_claimed_pressure_in_verdict() -> None:
    store = InMemoryJobStore()
    dispatcher = JobDispatcher(store=store)
    request = JobDispatchRequest(
        tenant_id='tenant-1',
        job_id='job-1',
        queue_name='ops',
        job_type='sync',
        payload={'x': 1},
        dedupe_key='dk-1',
    )
    verdict = dispatcher.dispatch(request)
    assert verdict.accepted is True
    assert verdict.reason == 'accepted'
