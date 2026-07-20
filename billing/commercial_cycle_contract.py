from __future__ import annotations

from calendar import monthrange
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from core.tenancy.normalization import require_tenant_id

CANON_BILLING_COMMERCIAL_CYCLE_CONTRACT = True

_SUPPORTED_CYCLE_INTERVALS = frozenset({"weekly", "monthly", "yearly"})


def utc_now() -> datetime:
    return datetime.now(UTC)


def require_aware_datetime(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def require_commercial_int(name: str, value: Any, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        comparator = ">=" if minimum == 0 else ">"
        boundary = minimum if minimum == 0 else minimum - 1
        raise ValueError(f"{name} must be {comparator} {boundary}")
    return value


def _require_bool(name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _require_mapping(name: str, value: Any) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


def _replace_year_safe(value: datetime, year: int) -> datetime:
    require_aware_datetime("value", value)
    require_commercial_int("year", year, minimum=1)
    day = min(value.day, monthrange(year, value.month)[1])
    return value.replace(year=year, day=day)


def _add_calendar_months(value: datetime, months: int) -> datetime:
    require_aware_datetime("value", value)
    require_commercial_int("months", months)
    total_month = (value.year * 12 + (value.month - 1)) + months
    year = total_month // 12
    month = total_month % 12 + 1
    if year < 1 or year > 9999:
        raise ValueError("calendar month result is out of range")
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


class SubscriptionLifecycleStatus(StrEnum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    GRACE = "grace"
    SUSPENDED = "suspended"
    CANCELED = "canceled"


class InvoiceLifecycleStatus(StrEnum):
    DRAFT = "draft"
    ISSUED = "issued"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    VOID = "void"
    CREDITED = "credited"
    UNCOLLECTIBLE = "uncollectible"


@dataclass(frozen=True)
class BillingCycleWindow:
    start_at: datetime
    end_at: datetime
    anchor: str = "monthly"

    def validate(self) -> None:
        require_aware_datetime("start_at", self.start_at)
        require_aware_datetime("end_at", self.end_at)
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be > start_at")
        normalized_anchor = str(self.anchor or "").strip().lower()
        if normalized_anchor not in _SUPPORTED_CYCLE_INTERVALS:
            raise ValueError("anchor must be weekly, monthly, or yearly")
        if self.anchor != normalized_anchor:
            raise ValueError("anchor must use canonical lowercase form")

    @property
    def duration_seconds(self) -> float:
        self.validate()
        return float((self.end_at - self.start_at).total_seconds())

    def contains(self, when: datetime) -> bool:
        self.validate()
        require_aware_datetime("when", when)
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
        if not str(self.subscription_id or "").strip():
            raise ValueError("subscription_id is required")
        if not str(self.plan_id or "").strip():
            raise ValueError("plan_id is required")
        if not isinstance(self.status, SubscriptionLifecycleStatus):
            raise ValueError("status must be SubscriptionLifecycleStatus")
        if not isinstance(self.cycle, BillingCycleWindow):
            raise ValueError("cycle must be BillingCycleWindow")
        self.cycle.validate()
        _require_mapping("metadata", self.metadata)
        for value, name in (
            (self.grace_until, "grace_until"),
            (self.trial_ends_at, "trial_ends_at"),
            (self.canceled_at, "canceled_at"),
        ):
            if value is not None:
                require_aware_datetime(name, value)
                if value < self.cycle.start_at:
                    raise ValueError(f"{name} must be >= cycle.start_at")
        if self.status is SubscriptionLifecycleStatus.TRIALING and self.trial_ends_at is None:
            raise ValueError("trialing subscription requires trial_ends_at")
        if self.status is SubscriptionLifecycleStatus.GRACE and self.grace_until is None:
            raise ValueError("grace subscription requires grace_until")
        if self.status is SubscriptionLifecycleStatus.CANCELED and self.canceled_at is None:
            raise ValueError("canceled subscription requires canceled_at")
        if self.status is not SubscriptionLifecycleStatus.CANCELED and self.canceled_at is not None:
            raise ValueError("canceled_at is only allowed for canceled subscription")


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
        if not str(self.invoice_id or "").strip():
            raise ValueError("invoice_id is required")
        require_commercial_int("amount_minor", self.amount_minor, minimum=0)
        if not str(self.currency or "").strip():
            raise ValueError("currency is required")
        if not str(self.provider_name or "").strip():
            raise ValueError("provider_name is required")
        if not str(self.idempotency_key or "").strip():
            raise ValueError("idempotency_key is required")
        require_commercial_int("attempt_no", self.attempt_no, minimum=1)
        require_aware_datetime("scheduled_at", self.scheduled_at)
        _require_mapping("metadata", self.metadata)


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
        if not str(self.invoice_id or "").strip():
            raise ValueError("invoice_id is required")
        if not str(self.provider_name or "").strip():
            raise ValueError("provider_name is required")
        _require_bool("successful", self.successful)
        _require_bool("retryable", self.retryable)
        require_aware_datetime("processed_at", self.processed_at)
        metadata = _require_mapping("metadata", self.metadata)
        if self.successful and self.retryable:
            raise ValueError("successful result cannot be retryable")
        if self.successful and self.failure_reason is not None and str(self.failure_reason).strip():
            raise ValueError("successful result cannot include failure_reason")
        if self.successful and not str(self.external_reference or "").strip() and not bool(metadata.get("noop")):
            raise ValueError("external_reference is required for successful result")
        if not self.successful and not str(self.failure_reason or "").strip():
            raise ValueError("failure_reason is required for unsuccessful result")
        if (
            not self.successful
            and self.external_reference is not None
            and str(self.external_reference).strip()
            and not bool(metadata.get("provider_reference_on_failure"))
        ):
            raise ValueError("external_reference on failure requires provider_reference_on_failure metadata flag")


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
        if not str(self.invoice_id or "").strip():
            raise ValueError("invoice_id is required")
        require_commercial_int("attempt_no", self.attempt_no, minimum=1)
        require_aware_datetime("execute_at", self.execute_at)
        if not str(self.channel or "").strip():
            raise ValueError("channel is required")
        if not str(self.template_key or "").strip():
            raise ValueError("template_key is required")
        _require_mapping("metadata", self.metadata)


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
        _require_bool("allowed", self.allowed)
        require_commercial_int("projected_minor", self.projected_minor, minimum=0)
        if self.limit_minor is not None:
            require_commercial_int("limit_minor", self.limit_minor, minimum=0)
        if self.remaining_minor is not None:
            require_commercial_int("remaining_minor", self.remaining_minor, minimum=0)
        if not str(self.reason or "").strip():
            raise ValueError("reason is required")
        _require_mapping("metadata", self.metadata)


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
        if not str(self.drift_key or "").strip():
            raise ValueError("drift_key is required")
        expected = require_commercial_int("expected_minor", self.expected_minor)
        observed = require_commercial_int("observed_minor", self.observed_minor)
        delta = require_commercial_int("delta_minor", self.delta_minor)
        if delta != observed - expected:
            raise ValueError("delta_minor must equal observed_minor - expected_minor")
        if not str(self.severity or "").strip():
            raise ValueError("severity is required")
        _require_mapping("details", self.details)


def next_cycle_window(*, current_start_at: datetime, interval: str) -> BillingCycleWindow:
    require_aware_datetime("current_start_at", current_start_at)
    normalized = str(interval or "monthly").strip().lower()
    if normalized not in _SUPPORTED_CYCLE_INTERVALS:
        raise ValueError("interval must be weekly, monthly, or yearly")
    if normalized == "weekly":
        end_at = current_start_at + timedelta(days=7)
    elif normalized == "yearly":
        end_at = _replace_year_safe(current_start_at, current_start_at.year + 1)
    else:
        end_at = _add_calendar_months(current_start_at, 1)
    window = BillingCycleWindow(start_at=current_start_at, end_at=end_at, anchor=normalized)
    window.validate()
    return window


__all__ = [
    "BillingCycleWindow",
    "CANON_BILLING_COMMERCIAL_CYCLE_CONTRACT",
    "CommercialCollectionAttempt",
    "CommercialCollectionResult",
    "DunningAction",
    "InvoiceLifecycleStatus",
    "ReconciliationDrift",
    "SpendGuardVerdict",
    "SubscriptionCommercialEnvelope",
    "SubscriptionLifecycleStatus",
    "next_cycle_window",
    "require_aware_datetime",
    "require_commercial_int",
    "utc_now",
]
