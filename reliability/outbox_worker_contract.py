from __future__ import annotations

"""Global outbox worker contract.

One shared infra contract for all transport delivery workers.
This module must stay purely operational.
"""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from typing import Any


CANON_OUTBOX_WORKER_CONTRACT = True


@dataclass(frozen=True)
class OutboxWorkerDescriptor:
    worker_id: str
    transport_name: str
    backend_name: str
    mode: str = "durable"
    supports_run_until_drained: bool = True

    def validate(self) -> None:
        if not str(self.worker_id or "").strip():
            raise ValueError("worker_id is required")
        if not str(self.transport_name or "").strip():
            raise ValueError("transport_name is required")
        if not str(self.backend_name or "").strip():
            raise ValueError("backend_name is required")


@dataclass(frozen=True)
class GlobalOutboxDeliveryReport:
    tenant_id: str
    processed: int = 0
    delivered: int = 0
    retried: int = 0
    dead_lettered: int = 0
    skipped: int = 0
    worker_reports: tuple[Any, ...] = field(default_factory=tuple)


@runtime_checkable
class GlobalOutboxWorker(Protocol):
    def descriptor(self) -> OutboxWorkerDescriptor:
        ...

    def run_once(self, *, tenant_id: str, limit: int | None = None) -> Any:
        ...

    def run_until_drained(self, *, tenant_id: str, max_batches: int = 100) -> Any:
        ...


__all__ = [
    "CANON_OUTBOX_WORKER_CONTRACT",
    "GlobalOutboxDeliveryReport",
    "GlobalOutboxWorker",
    "OutboxWorkerDescriptor",
]
