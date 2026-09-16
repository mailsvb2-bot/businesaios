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

PAYMENT_SCHEMA_VERSION = 2
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
    business_id: str
    product_id: str
    order_id: str
    provider: str
    external_id: str
    schema_version: int = PAYMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        tenant = str(self.tenant_id or "").strip()
        business = str(self.business_id or "").strip()
        product = str(self.product_id or "").strip()
        order = str(self.order_id or "").strip()
        provider = str(self.provider or "").strip().lower()
        if not tenant:
            raise ValueError("payment tenant_id is required")
        if not business:
            raise ValueError("payment business_id is required")
        if not product:
            raise ValueError("payment product_id is required")
        if not order:
            raise ValueError("payment order_id is required")
        if not provider:
            raise ValueError("payment provider is required")
        if int(self.schema_version) != PAYMENT_SCHEMA_VERSION:
            raise ValueError("unsupported payment schema_version")
        object.__setattr__(self, "tenant_id", tenant)
        object.__setattr__(self, "business_id", business)
        object.__setattr__(self, "product_id", product)
        object.__setattr__(self, "order_id", order)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "external_id", validate_payment_external_id(self.external_id))


@dataclass(frozen=True, slots=True)
class Payment:
    """Canonical PII-free payment entity projected from v2 chronology."""

    identity: PaymentIdentity
    amount_minor: int
    currency: str
    lifecycle_status: PaymentLifecycleStatus = PaymentLifecycleStatus.CREATED
    created_at_ms: int = 0
    updated_at_ms: int = 0
    terminal_at_ms: int | None = None
    captured_at_ms: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.identity, PaymentIdentity):
            raise ValueError("payment identity is required")
        if isinstance(self.amount_minor, bool) or int(self.amount_minor) <= 0:
            raise ValueError("payment amount_minor must be positive")
        currency = str(self.currency or "").strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("payment currency must be a three-letter code")
        status = PaymentLifecycleStatus(self.lifecycle_status)
        created = int(self.created_at_ms)
        updated = int(self.updated_at_ms)
        if created < 0 or updated < created:
            raise ValueError("payment timestamps are invalid")
        terminal = None if self.terminal_at_ms is None else int(self.terminal_at_ms)
        captured = None if self.captured_at_ms is None else int(self.captured_at_ms)
        if terminal is not None and terminal < created:
            raise ValueError("payment terminal_at_ms is invalid")
        if captured is not None and captured < created:
            raise ValueError("payment captured_at_ms is invalid")
        if (
            status in {PaymentLifecycleStatus.CREATED, PaymentLifecycleStatus.CHECKED}
            and (terminal is not None or captured is not None)
        ):
            raise ValueError("non-terminal payment cannot have terminal timestamps")
        if status is PaymentLifecycleStatus.FAILED and (
            terminal is None or captured is not None
        ):
            raise ValueError("failed payment requires terminal_at_ms only")
        if status is PaymentLifecycleStatus.SUCCEEDED:
            if (terminal is None) != (captured is None):
                raise ValueError("captured payment terminal timestamps must match")
            if terminal is not None and terminal != captured:
                raise ValueError("captured payment timestamps conflict")
        object.__setattr__(self, "amount_minor", int(self.amount_minor))
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "lifecycle_status", status)
        object.__setattr__(self, "created_at_ms", created)
        object.__setattr__(self, "updated_at_ms", updated)
        object.__setattr__(self, "terminal_at_ms", terminal)
        object.__setattr__(self, "captured_at_ms", captured)


__all__ = [
    "CANON_PAYMENT_SEMANTIC_CONTRACT",
    "PAYMENT_SCHEMA_VERSION",
    "PAYMENT_TERMINAL_EVENT_TYPES",
    "Payment",
    "PaymentIdentity",
    "PaymentLifecycleStatus",
    "payment_lifecycle_status_for_event",
    "validate_payment_external_id",
]
