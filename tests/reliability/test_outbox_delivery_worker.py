from __future__ import annotations

from reliability.outbox_backend import (
    OutboxBackendHealth,
    OutboxBackendMode,
    OutboxDeliveryConflict,
    OutboxDeliveryReceipt,
    OutboxDeliveryStatus,
)
from reliability.outbox_delivery_worker import OutboxDeliveryWorker
from reliability.outbox_store import InMemoryOutboxStore, OutboxMessage, OutboxState


class _ConflictBackend:
    backend_name = 'conflict'

    def healthcheck(self) -> OutboxBackendHealth:
        return OutboxBackendHealth(backend_name=self.backend_name, healthy=True, mode=OutboxBackendMode.DURABLE)

    def get_receipt(self, *, tenant_id: str, message_id: str):
        return None

    def deliver(self, message: OutboxMessage):
        raise OutboxDeliveryConflict('payload drift')


class _FlakyBackend:
    backend_name = 'flaky'

    def __init__(self) -> None:
        self.calls = 0

    def healthcheck(self) -> OutboxBackendHealth:
        return OutboxBackendHealth(backend_name=self.backend_name, healthy=True, mode=OutboxBackendMode.DURABLE)

    def get_receipt(self, *, tenant_id: str, message_id: str):
        return None

    def deliver(self, message: OutboxMessage):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError('temporary failure')
        return OutboxDeliveryReceipt(
            tenant_id=message.tenant_id,
            message_id=message.message_id,
            backend_name=self.backend_name,
            status=OutboxDeliveryStatus.DELIVERED,
        )


class _UnhealthyBackend:
    backend_name = 'unhealthy'

    def healthcheck(self) -> OutboxBackendHealth:
        return OutboxBackendHealth(backend_name=self.backend_name, healthy=False, mode=OutboxBackendMode.DURABLE, detail='disk offline')

    def get_receipt(self, *, tenant_id: str, message_id: str):
        return None

    def deliver(self, message: OutboxMessage):
        raise AssertionError('deliver must not be called when unhealthy')



def test_outbox_delivery_worker_moves_conflict_to_dead_letter() -> None:
    store = InMemoryOutboxStore()
    store.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='msg-1', topic='effects', dedupe_key='d-1', payload={'ok': True}))

    report = OutboxDeliveryWorker(outbox_store=store, backend=_ConflictBackend()).run_once(tenant_id='tenant-a')
    assert report.dead_lettered == 1
    assert store.get(tenant_id='tenant-a', message_id='msg-1').state is OutboxState.DEAD



def test_outbox_delivery_worker_retries_then_delivers() -> None:
    store = InMemoryOutboxStore()
    store.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='msg-1', topic='effects', dedupe_key='d-1', payload={'ok': True}))
    backend = _FlakyBackend()
    worker = OutboxDeliveryWorker(outbox_store=store, backend=backend)

    first = worker.run_once(tenant_id='tenant-a')
    assert first.retried == 1
    msg = store.get(tenant_id='tenant-a', message_id='msg-1')
    assert msg.state is OutboxState.PENDING

    msg = store.get(tenant_id='tenant-a', message_id='msg-1')
    claimed_ready = OutboxMessage(
        tenant_id=msg.tenant_id,
        message_id=msg.message_id,
        topic=msg.topic,
        dedupe_key=msg.dedupe_key,
        payload=msg.payload,
        state=msg.state,
        created_at=msg.created_at,
        updated_at=msg.updated_at,
        available_at=msg.created_at,
        claim_owner_id=msg.claim_owner_id,
        claim_expires_at=msg.claim_expires_at,
        delivery_attempts=msg.delivery_attempts,
        last_error=msg.last_error,
        trace_id=msg.trace_id,
        run_id=msg.run_id,
        decision_id=msg.decision_id,
    )
    store._messages[(claimed_ready.tenant_id, claimed_ready.message_id)] = claimed_ready  # type: ignore[attr-defined]

    second = worker.run_once(tenant_id='tenant-a')
    assert second.delivered == 1
    assert store.get(tenant_id='tenant-a', message_id='msg-1').state is OutboxState.DELIVERED



def test_outbox_delivery_worker_skips_unhealthy_backend() -> None:
    store = InMemoryOutboxStore()
    store.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='msg-1', topic='effects', dedupe_key='d-1', payload={'ok': True}))

    report = OutboxDeliveryWorker(outbox_store=store, backend=_UnhealthyBackend()).run_once(tenant_id='tenant-a')
    assert report.processed == 0
    assert report.skipped == 1
    assert store.get(tenant_id='tenant-a', message_id='msg-1').state is OutboxState.PENDING
