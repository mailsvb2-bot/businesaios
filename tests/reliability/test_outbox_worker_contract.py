from __future__ import annotations

from reliability.outbox_backend import OutboxBackendHealth, OutboxBackendMode
from reliability.outbox_delivery_worker import OutboxDeliveryWorker
from reliability.outbox_store import InMemoryOutboxStore
from reliability.outbox_worker_contract import GlobalOutboxWorker


class _HealthyBackend:
    backend_name = 'file_outbox_backend'

    def healthcheck(self) -> OutboxBackendHealth:
        return OutboxBackendHealth(backend_name=self.backend_name, healthy=True, mode=OutboxBackendMode.DURABLE)

    def get_receipt(self, *, tenant_id: str, message_id: str):
        return None

    def deliver(self, message):
        raise AssertionError('not used')


def test_outbox_delivery_worker_implements_global_contract() -> None:
    worker = OutboxDeliveryWorker(outbox_store=InMemoryOutboxStore(), backend=_HealthyBackend(), transport_name='effects')
    assert isinstance(worker, GlobalOutboxWorker)
    descriptor = worker.descriptor()
    assert descriptor.transport_name == 'effects'
    assert descriptor.backend_name == 'file_outbox_backend'
