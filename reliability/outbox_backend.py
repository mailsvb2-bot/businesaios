from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Protocol, runtime_checkable

from reliability.outbox_store import OutboxMessage


CANON_OUTBOX_BACKEND = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OutboxDeliveryStatus(str, Enum):
    DELIVERED = "delivered"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"


class OutboxBackendMode(str, Enum):
    DURABLE = "durable"
    BEST_EFFORT = "best_effort"


@dataclass(frozen=True)
class OutboxBackendHealth:
    backend_name: str
    healthy: bool
    checked_at: datetime = field(default_factory=utc_now)
    mode: OutboxBackendMode = OutboxBackendMode.DURABLE
    detail: str = ""

    def validate(self) -> None:
        if not str(self.backend_name or "").strip():
            raise ValueError("backend_name is required")
        if self.checked_at.tzinfo is None:
            raise ValueError("checked_at must be timezone-aware")


@dataclass(frozen=True)
class OutboxDeliveryReceipt:
    tenant_id: str
    message_id: str
    backend_name: str
    status: OutboxDeliveryStatus
    delivered_at: datetime = field(default_factory=utc_now)
    external_id: str | None = None
    payload_digest: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")
        if not str(self.message_id or "").strip():
            raise ValueError("message_id is required")
        if not str(self.backend_name or "").strip():
            raise ValueError("backend_name is required")
        if self.delivered_at.tzinfo is None:
            raise ValueError("delivered_at must be timezone-aware")


@dataclass(frozen=True)
class OutboxDeliveryRecord:
    receipt: OutboxDeliveryReceipt
    topic: str
    dedupe_key: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        self.receipt.validate()
        if not str(self.topic or "").strip():
            raise ValueError("topic is required")
        if not str(self.dedupe_key or "").strip():
            raise ValueError("dedupe_key is required")


class OutboxDeliveryError(Exception):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = True,
        code: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = bool(retryable)
        self.code = None if code is None else str(code)
        self.details = dict(details or {})


class OutboxDeliveryConflict(OutboxDeliveryError):
    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message, retryable=False, code="delivery_conflict", details=details)


@runtime_checkable
class OutboxBackend(Protocol):
    backend_name: str

    def deliver(self, message: OutboxMessage) -> OutboxDeliveryReceipt:
        """
        Idempotent delivery keyed by tenant_id + message_id.
        Re-delivery of the same semantic message should return DUPLICATE,
        while payload drift for the same identity must raise conflict.
        """
        ...

    def get_receipt(self, *, tenant_id: str, message_id: str) -> OutboxDeliveryReceipt | None:
        ...

    def healthcheck(self) -> OutboxBackendHealth:
        ...


@runtime_checkable
class OutboxBackendInspector(Protocol):
    backend_name: str

    def get_record(self, *, tenant_id: str, message_id: str) -> OutboxDeliveryRecord | None:
        ...

    def list_records(
        self,
        *,
        tenant_id: str,
        topic: str | None = None,
        limit: int = 100,
    ) -> tuple[OutboxDeliveryRecord, ...]:
        ...


__all__ = [
    "CANON_OUTBOX_BACKEND",
    "OutboxBackend",
    "OutboxBackendHealth",
    "OutboxBackendInspector",
    "OutboxBackendMode",
    "OutboxDeliveryConflict",
    "OutboxDeliveryError",
    "OutboxDeliveryReceipt",
    "OutboxDeliveryRecord",
    "OutboxDeliveryStatus",
    "utc_now",
]
