from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping
from uuid import uuid4

from billing.ledger_event import utc_now
from core.tenancy.normalization import require_tenant_id

CANON_BILLING_RECOVERY_CONTRACTS = True


@dataclass(frozen=True)
class ChargebackCase:
    tenant_id: str
    invoice_id: str
    user_id: str
    amount_minor: int
    currency: str
    reason: str
    opened_at: datetime = field(default_factory=utc_now)
    case_id: str = field(default_factory=lambda: str(uuid4()))
    idempotency_key: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.invoice_id or '').strip():
            raise ValueError('invoice_id is required')
        if not str(self.user_id or '').strip():
            raise ValueError('user_id is required')
        if int(self.amount_minor) <= 0:
            raise ValueError('amount_minor must be > 0')
        if not str(self.currency or '').strip():
            raise ValueError('currency is required')
        if not str(self.reason or '').strip():
            raise ValueError('reason is required')
        if self.opened_at.tzinfo is None:
            raise ValueError('opened_at must be timezone-aware')
        if self.idempotency_key is not None and not str(self.idempotency_key).strip():
            raise ValueError('idempotency_key cannot be blank')


@dataclass(frozen=True)
class RefundResult:
    tenant_id: str
    invoice_id: str
    refund_id: str
    amount_minor: int
    currency: str
    provider_name: str
    external_reference: str
    processed_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.invoice_id or '').strip():
            raise ValueError('invoice_id is required')
        if not str(self.refund_id or '').strip():
            raise ValueError('refund_id is required')
        if int(self.amount_minor) <= 0:
            raise ValueError('amount_minor must be > 0')
        if not str(self.currency or '').strip():
            raise ValueError('currency is required')
        if not str(self.provider_name or '').strip():
            raise ValueError('provider_name is required')
        if not str(self.external_reference or '').strip():
            raise ValueError('external_reference is required')
        if self.processed_at.tzinfo is None:
            raise ValueError('processed_at must be timezone-aware')


__all__ = ["CANON_BILLING_RECOVERY_CONTRACTS", "ChargebackCase", "RefundResult"]
