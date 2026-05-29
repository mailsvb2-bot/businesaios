from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from decimal import Decimal
from typing import Mapping
from uuid import uuid4

CANON_RUNTIME_MONETIZATION_CONTRACTS = True


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Money:
    amount_minor: int
    currency: str = 'USD'

    def __post_init__(self) -> None:
        if int(self.amount_minor) < 0:
            raise ValueError('amount_minor must be >= 0')
        if not str(self.currency or '').strip():
            raise ValueError('currency is required')

    @property
    def decimal_amount(self) -> Decimal:
        return (Decimal(self.amount_minor) / Decimal('100')).quantize(Decimal('0.01'))


@dataclass(frozen=True, slots=True)
class MonetizationPlan:
    plan_id: str
    display_name: str
    currency: str
    interval: str
    amount_minor: int
    included_usage: Mapping[str, float] = field(default_factory=dict)
    included_seats: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.plan_id or '').strip():
            raise ValueError('plan_id is required')
        if not str(self.display_name or '').strip():
            raise ValueError('display_name is required')
        if not str(self.currency or '').strip():
            raise ValueError('currency is required')
        if not str(self.interval or '').strip():
            raise ValueError('interval is required')
        if int(self.amount_minor) < 0:
            raise ValueError('amount_minor must be >= 0')
        if int(self.included_seats) < 0:
            raise ValueError('included_seats must be >= 0')


@dataclass(frozen=True, slots=True)
class TaxContext:
    country_code: str
    is_business_customer: bool = False
    tax_id: str | None = None


@dataclass(frozen=True, slots=True)
class TaxBreakdown:
    regime: str
    tax_rate_bps: int
    tax_amount_minor: int
    reverse_charge_applied: bool = False
    evidence_key: str | None = None


@dataclass(frozen=True, slots=True)
class CheckoutSession:
    session_id: str
    tenant_id: str
    user_id: str
    plan_id: str
    checkout_url: str
    created_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SubscriptionRecord:
    subscription_id: str
    tenant_id: str
    user_id: str
    plan_id: str
    status: str
    started_at: datetime = field(default_factory=utc_now)
    current_period_end_at: datetime | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class InvoiceRecord:
    invoice_id: str
    subscription_id: str | None
    tenant_id: str
    user_id: str
    subtotal_minor: int
    tax_minor: int
    total_minor: int
    currency: str
    status: str
    created_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RefundRecord:
    refund_id: str
    tenant_id: str
    user_id: str
    amount_minor: int
    currency: str
    reason: str
    status: str = 'processed'
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class ChargebackRecord:
    chargeback_id: str
    tenant_id: str
    user_id: str
    amount_minor: int
    currency: str
    reason: str
    status: str = 'opened'
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class MonetizationDashboardSnapshot:
    tenant_id: str
    gross_revenue_minor: int
    refunded_minor: int
    chargeback_minor: int
    net_revenue_minor: int
    active_subscriptions: int
    past_due_subscriptions: int
    cancelled_subscriptions: int
    currency: str = 'USD'


__all__ = [
    'CANON_RUNTIME_MONETIZATION_CONTRACTS',
    'ChargebackRecord',
    'CheckoutSession',
    'InvoiceRecord',
    'Money',
    'MonetizationDashboardSnapshot',
    'MonetizationPlan',
    'RefundRecord',
    'SubscriptionRecord',
    'TaxBreakdown',
    'TaxContext',
    'utc_now',
]
