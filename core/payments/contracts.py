from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from core.events.event_types import (
    PAYMENT_CAPTURED,
    PAYMENT_CHECKED,
    PAYMENT_CREATED,
    PAYMENT_FAILED,
    PAYMENT_SUCCEEDED,
)

PAYMENT_SCHEMA_VERSION = 1
CANON_PAYMENT_SEMANTIC_CONTRACT = True
PAYMENT_TERMINAL_EVENT_TYPES = frozenset({PAYMENT_CAPTURED, PAYMENT_FAILED})

_EXTERNAL_ID_RE = re.compile(r"^[A-Za-z0-9_\-:.]{6,200}$")


class PaymentLifecycleStatus(str, Enum):
    CREATED = "created"
    CHECKED = "checked"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


def validate_payment_external_id(external_id: str) -> str:
    ext = str(external_id or "").strip()
    if not ext:
        raise ValueError("payment_created.external_id is required")
    if not _EXTERNAL_ID_RE.match(ext):
        raise ValueError("payment_created.external_id has invalid format")
    return ext


def payment_lifecycle_status_for_event(event_type: str) -> PaymentLifecycleStatus:
    event = str(event_type or "").strip()
    if event == PAYMENT_CREATED:
        return PaymentLifecycleStatus.CREATED
    if event == PAYMENT_CHECKED:
        return PaymentLifecycleStatus.CHECKED
    if event in {PAYMENT_CAPTURED, PAYMENT_SUCCEEDED}:
        return PaymentLifecycleStatus.SUCCEEDED
    if event == PAYMENT_FAILED:
        return PaymentLifecycleStatus.FAILED
    raise ValueError(f"unknown canonical payment lifecycle event: {event}")


@dataclass(frozen=True, slots=True)
class PaymentIdentity:
    tenant_id: str
    product_id: str
    order_id: str
    provider: str
    external_id: str
    schema_version: int = PAYMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        tenant = str(self.tenant_id or "").strip()
        product = str(self.product_id or "").strip()
        order = str(self.order_id or "").strip()
        provider = str(self.provider or "").strip().lower()
        if not tenant:
            raise ValueError("payment tenant_id is required")
        if not product:
            raise ValueError("payment product_id is required")
        if not order:
            raise ValueError("payment order_id is required")
        if not provider:
            raise ValueError("payment provider is required")
        if int(self.schema_version) != PAYMENT_SCHEMA_VERSION:
            raise ValueError("unsupported payment schema_version")
        object.__setattr__(self, "tenant_id", tenant)
        object.__setattr__(self, "product_id", product)
        object.__setattr__(self, "order_id", order)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "external_id", validate_payment_external_id(self.external_id))


__all__ = [
    "CANON_PAYMENT_SEMANTIC_CONTRACT",
    "PAYMENT_SCHEMA_VERSION",
    "PAYMENT_TERMINAL_EVENT_TYPES",
    "PaymentIdentity",
    "PaymentLifecycleStatus",
    "payment_lifecycle_status_for_event",
    "validate_payment_external_id",
]
