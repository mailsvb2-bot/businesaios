from __future__ import annotations

from reliability.execution_checkpoint_store import InMemoryExecutionCheckpointStore
from reliability.idempotency_store import InMemoryIdempotencyStore
from reliability.outbox_delivery_worker import OutboxDeliveryWorker
from reliability.outbox_store import InMemoryOutboxStore, OutboxMessage
from reliability.outbox_backend import OutboxBackendHealth, OutboxBackendMode, OutboxDeliveryReceipt, OutboxDeliveryStatus
from reliability.recovery_orchestrator import RecoveryOrchestrator


class _Backend:
    def __init__(self, backend_name: str) -> None:
        self.backend_name = backend_name

    def healthcheck(self) -> OutboxBackendHealth:
        return OutboxBackendHealth(backend_name=self.backend_name, healthy=True, mode=OutboxBackendMode.DURABLE)

    def get_receipt(self, *, tenant_id: str, message_id: str):
        return None

    def deliver(self, message: OutboxMessage) -> OutboxDeliveryReceipt:
        return OutboxDeliveryReceipt(
            tenant_id=message.tenant_id,
            message_id=message.message_id,
            backend_name=self.backend_name,
            status=OutboxDeliveryStatus.DELIVERED,
        )


def test_recovery_orchestrator_recovers_all_registered_transports() -> None:
    email_store = InMemoryOutboxStore()
    sms_store = InMemoryOutboxStore()
    email_store.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='email-1', topic='email', dedupe_key='email-1', payload={'transport': 'email'}))
    sms_store.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='sms-1', topic='sms', dedupe_key='sms-1', payload={'transport': 'sms'}))

    orchestrator = RecoveryOrchestrator(
        checkpoint_store=InMemoryExecutionCheckpointStore(),
        idempotency_store=InMemoryIdempotencyStore(),
        outbox_store=email_store,
        transport_workers={
            'email': OutboxDeliveryWorker(outbox_store=email_store, backend=_Backend('email_backend'), transport_name='email'),
            'sms': OutboxDeliveryWorker(outbox_store=sms_store, backend=_Backend('sms_backend'), transport_name='sms'),
        },
    )

    report = orchestrator.recover_all_transports(tenant_id='tenant-a')
    assert report.delivered == 2
    assert len(report.worker_reports) == 2
