from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Mapping

from core.tenancy.normalization import require_tenant_id

CANON_BILLING_COMMERCIAL_CYCLE_CONTRACT = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _replace_year_safe(value: datetime, year: int) -> datetime:
    day = min(value.day, monthrange(year, value.month)[1])
    return value.replace(year=year, day=day)


def _add_calendar_months(value: datetime, months: int) -> datetime:
    if value.tzinfo is None:
        raise ValueError('value must be timezone-aware')
    total_month = (value.year * 12 + (value.month - 1)) + int(months)
    year = total_month // 12
    month = total_month % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


class SubscriptionLifecycleStatus(str, Enum):
    TRIALING = 'trialing'
    ACTIVE = 'active'
    PAST_DUE = 'past_due'
    GRACE = 'grace'
    SUSPENDED = 'suspended'
    CANCELED = 'canceled'


class InvoiceLifecycleStatus(str, Enum):
    DRAFT = 'draft'
    ISSUED = 'issued'
    PARTIALLY_PAID = 'partially_paid'
    PAID = 'paid'
    VOID = 'void'
    CREDITED = 'credited'
    UNCOLLECTIBLE = 'uncollectible'


@dataclass(frozen=True)
class BillingCycleWindow:
    start_at: datetime
    end_at: datetime
    anchor: str = 'monthly'

    def validate(self) -> None:
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError('cycle timestamps must be timezone-aware')
        if self.end_at <= self.start_at:
            raise ValueError('end_at must be > start_at')
        if not str(self.anchor or '').strip():
            raise ValueError('anchor is required')

    @property
    def duration_seconds(self) -> float:
        self.validate()
        return float((self.end_at - self.start_at).total_seconds())

    def contains(self, when: datetime) -> bool:
        self.validate()
        if when.tzinfo is None:
            raise ValueError('when must be timezone-aware')
        return self.start_at <= when < self.end_at


@dataclass(frozen=True)
class SubscriptionCommercialEnvelope:
    tenant_id: str
    subscription_id: str
    plan_id: str
    status: SubscriptionLifecycleStatus
    cycle: BillingCycleWindow
    grace_until: datetime | None = None
    trial_ends_at: datetime | None = None
    canceled_at: datetime | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.subscription_id or '').strip():
            raise ValueError('subscription_id is required')
        if not str(self.plan_id or '').strip():
            raise ValueError('plan_id is required')
        self.cycle.validate()
        for value, name in (
            (self.grace_until, 'grace_until'),
            (self.trial_ends_at, 'trial_ends_at'),
            (self.canceled_at, 'canceled_at'),
        ):
            if value is not None and value.tzinfo is None:
                raise ValueError(f'{name} must be timezone-aware')
        if self.trial_ends_at is not None and self.trial_ends_at < self.cycle.start_at:
            raise ValueError('trial_ends_at must be >= cycle.start_at')
        if self.grace_until is not None and self.grace_until < self.cycle.start_at:
            raise ValueError('grace_until must be >= cycle.start_at')
        if self.status is SubscriptionLifecycleStatus.TRIALING and self.trial_ends_at is None:
            raise ValueError('trialing subscription requires trial_ends_at')
        if self.status is SubscriptionLifecycleStatus.GRACE and self.grace_until is None:
            raise ValueError('grace subscription requires grace_until')
        if self.status is SubscriptionLifecycleStatus.CANCELED and self.canceled_at is None:
            raise ValueError('canceled subscription requires canceled_at')
        if self.status is not SubscriptionLifecycleStatus.CANCELED and self.canceled_at is not None:
            raise ValueError('canceled_at is only allowed for canceled subscription')


@dataclass(frozen=True)
class CommercialCollectionAttempt:
    invoice_id: str
    tenant_id: str
    amount_minor: int
    currency: str
    provider_name: str
    idempotency_key: str
    attempt_no: int = 1
    scheduled_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.invoice_id or '').strip():
            raise ValueError('invoice_id is required')
        if int(self.amount_minor) < 0:
            raise ValueError('amount_minor must be >= 0')
        if not str(self.currency or '').strip():
            raise ValueError('currency is required')
        if not str(self.provider_name or '').strip():
            raise ValueError('provider_name is required')
        if not str(self.idempotency_key or '').strip():
            raise ValueError('idempotency_key is required')
        if int(self.attempt_no) <= 0:
            raise ValueError('attempt_no must be > 0')
        if self.scheduled_at.tzinfo is None:
            raise ValueError('scheduled_at must be timezone-aware')


@dataclass(frozen=True)
class CommercialCollectionResult:
    invoice_id: str
    tenant_id: str
    provider_name: str
    successful: bool
    external_reference: str | None = None
    failure_reason: str | None = None
    retryable: bool = False
    processed_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.invoice_id or '').strip():
            raise ValueError('invoice_id is required')
        if not str(self.provider_name or '').strip():
            raise ValueError('provider_name is required')
        if self.processed_at.tzinfo is None:
            raise ValueError('processed_at must be timezone-aware')
        if self.successful and self.failure_reason is not None and str(self.failure_reason).strip():
            raise ValueError('successful result cannot include failure_reason')
        if self.successful and not str(self.external_reference or '').strip() and not bool(dict(self.metadata).get('noop')):
            raise ValueError('external_reference is required for successful result')
        if not self.successful and not str(self.failure_reason or '').strip():
            raise ValueError('failure_reason is required for unsuccessful result')
        if not self.successful and self.external_reference is not None and str(self.external_reference).strip() and not bool(dict(self.metadata).get('provider_reference_on_failure')):
            raise ValueError('external_reference on failure requires provider_reference_on_failure metadata flag')


@dataclass(frozen=True)
class DunningAction:
    invoice_id: str
    tenant_id: str
    attempt_no: int
    execute_at: datetime
    channel: str
    template_key: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.invoice_id or '').strip():
            raise ValueError('invoice_id is required')
        if int(self.attempt_no) <= 0:
            raise ValueError('attempt_no must be > 0')
        if self.execute_at.tzinfo is None:
            raise ValueError('execute_at must be timezone-aware')
        if not str(self.channel or '').strip():
            raise ValueError('channel is required')
        if not str(self.template_key or '').strip():
            raise ValueError('template_key is required')


@dataclass(frozen=True)
class SpendGuardVerdict:
    tenant_id: str
    allowed: bool
    projected_minor: int
    limit_minor: int | None
    remaining_minor: int | None
    reason: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if int(self.projected_minor) < 0:
            raise ValueError('projected_minor must be >= 0')
        if self.limit_minor is not None and int(self.limit_minor) < 0:
            raise ValueError('limit_minor must be >= 0')
        if self.remaining_minor is not None and int(self.remaining_minor) < 0:
            raise ValueError('remaining_minor must be >= 0')
        if not str(self.reason or '').strip():
            raise ValueError('reason is required')


@dataclass(frozen=True)
class ReconciliationDrift:
    tenant_id: str
    drift_key: str
    expected_minor: int
    observed_minor: int
    delta_minor: int
    severity: str
    details: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.drift_key or '').strip():
            raise ValueError('drift_key is required')
        if not str(self.severity or '').strip():
            raise ValueError('severity is required')


def next_cycle_window(*, current_start_at: datetime, interval: str) -> BillingCycleWindow:
    if current_start_at.tzinfo is None:
        raise ValueError('current_start_at must be timezone-aware')
    normalized = str(interval or 'monthly').strip().lower()
    if normalized == 'weekly':
        end_at = current_start_at + timedelta(days=7)
    elif normalized == 'yearly':
        end_at = _replace_year_safe(current_start_at, current_start_at.year + 1)
    else:
        normalized = 'monthly'
        end_at = _add_calendar_months(current_start_at, 1)
    window = BillingCycleWindow(start_at=current_start_at, end_at=end_at, anchor=normalized)
    window.validate()
    return window


__all__ = [
    'BillingCycleWindow',
    'CANON_BILLING_COMMERCIAL_CYCLE_CONTRACT',
    'CommercialCollectionAttempt',
    'CommercialCollectionResult',
    'DunningAction',
    'InvoiceLifecycleStatus',
    'ReconciliationDrift',
    'SpendGuardVerdict',
    'SubscriptionCommercialEnvelope',
    'SubscriptionLifecycleStatus',
    'next_cycle_window',
    'utc_now',
]
