from __future__ import annotations

from observability.delivery_metrics import DeliveryObservabilityMetrics
from reliability.outbox_backend import OutboxBackendHealth, OutboxBackendMode, OutboxDeliveryReceipt, OutboxDeliveryStatus
from reliability.outbox_delivery_worker import OutboxDeliveryWorker
from reliability.outbox_store import InMemoryOutboxStore, OutboxMessage, OutboxState


class _Backend:
    backend_name = 'sqlite_outbox_backend'

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
            metadata={'transport': 'email'},
        )


def test_outbox_delivery_worker_emits_observability_metrics() -> None:
    store = InMemoryOutboxStore()
    store.enqueue(
        OutboxMessage(
            tenant_id='tenant-a',
            message_id='msg-1',
            topic='email',
            dedupe_key='dedupe-1',
            payload={'subject': 'Hello', 'transport': 'email'},
        )
    )
    metrics = DeliveryObservabilityMetrics()
    report = OutboxDeliveryWorker(
        outbox_store=store,
        backend=_Backend(),
        transport_name='email',
        metrics=metrics,
    ).run_once(tenant_id='tenant-a')

    assert report.delivered == 1
    assert store.get(tenant_id='tenant-a', message_id='msg-1').state is OutboxState.DELIVERED
    snapshot = metrics.snapshot()
    assert snapshot['counters']['delivery.worker.healthcheck.total'] == 1
