from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Mapping, Protocol

from tenancy.tenant_contract import TenantPlan, utc_now

CANON_BILLING_PLAN_CONTRACT = True


class BillingMeterKey:
    """Canonical commercial meter keys.

    Constants only. This is not a second plan/decision owner.
    """

    ACTIONS = "actions"
    CONNECTOR_CALLS = "connector_calls"
    OUTBOUND_MESSAGES = "outbound_messages"
    MEMORY_WRITES = "memory_writes"
    PUBLICATIONS = "publications"
    STORAGE_GB_HOURS = "storage_gb_hours"
    API_REQUESTS = "api_requests"
    CUSTOM = "custom"


@dataclass(frozen=True)
class PlanQuotaLimit:
    dimension: str
    limit: float
    window: str = "day"
    hard_stop: bool = True
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.dimension or "").strip():
            raise ValueError("dimension is required")
        if not str(self.window or "").strip():
            raise ValueError("window is required")
        if float(self.limit) < 0:
            raise ValueError("limit must be >= 0")

    def normalized_copy(self) -> "PlanQuotaLimit":
        self.validate()
        return replace(
            self,
            dimension=str(self.dimension).strip(),
            window=str(self.window).strip().lower(),
            limit=float(self.limit),
            hard_stop=bool(self.hard_stop),
            metadata=dict(self.metadata),
        )


@dataclass(frozen=True)
class PlanRateCardItem:
    meter_key: str
    unit_price: float
    currency: str = "USD"
    unit_name: str = "unit"
    included_units: float = 0.0
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.meter_key or "").strip():
            raise ValueError("meter_key is required")
        if not str(self.currency or "").strip():
            raise ValueError("currency is required")
        if not str(self.unit_name or "").strip():
            raise ValueError("unit_name is required")
        if float(self.unit_price) < 0:
            raise ValueError("unit_price must be >= 0")
        if float(self.included_units) < 0:
            raise ValueError("included_units must be >= 0")

    def normalized_copy(self) -> "PlanRateCardItem":
        self.validate()
        return replace(
            self,
            meter_key=str(self.meter_key).strip(),
            unit_price=float(self.unit_price),
            currency=str(self.currency).strip().upper(),
            unit_name=str(self.unit_name).strip(),
            included_units=float(self.included_units),
            metadata=dict(self.metadata),
        )

    def billable_units(self, quantity: float) -> float:
        requested = float(quantity)
        if requested < 0:
            raise ValueError("quantity must be >= 0")
        return max(0.0, requested - float(self.included_units))

    def charge_for(self, quantity: float) -> float:
        return round(self.billable_units(quantity) * float(self.unit_price), 6)


@dataclass(frozen=True)
class BillingPlanSpec:
    plan_id: TenantPlan
    display_name: str
    version: str = "v1"
    quota_limits: tuple[PlanQuotaLimit, ...] = field(default_factory=tuple)
    rate_card: tuple[PlanRateCardItem, ...] = field(default_factory=tuple)
    features: Mapping[str, bool] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        if not isinstance(self.plan_id, TenantPlan):
            raise ValueError("plan_id must be a TenantPlan")
        if not str(self.display_name or "").strip():
            raise ValueError("display_name is required")
        if not str(self.version or "").strip():
            raise ValueError("version is required")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")

        seen_quota_keys: set[tuple[str, str]] = set()
        seen_meters: set[str] = set()
        for quota in self.quota_limits:
            normalized = quota.normalized_copy()
            quota_key = (normalized.dimension, normalized.window)
            if quota_key in seen_quota_keys:
                raise ValueError(f"duplicate plan quota: {quota_key}")
            seen_quota_keys.add(quota_key)
        for item in self.rate_card:
            normalized_item = item.normalized_copy()
            if normalized_item.meter_key in seen_meters:
                raise ValueError(f"duplicate rate card meter: {normalized_item.meter_key}")
            seen_meters.add(normalized_item.meter_key)

    def normalized_copy(self) -> "BillingPlanSpec":
        self.validate()
        return replace(
            self,
            display_name=str(self.display_name).strip(),
            version=str(self.version).strip(),
            quota_limits=tuple(item.normalized_copy() for item in self.quota_limits),
            rate_card=tuple(item.normalized_copy() for item in self.rate_card),
            features={str(k): bool(v) for k, v in dict(self.features).items()},
            metadata=dict(self.metadata),
        )

    def quota_for(self, dimension: str, *, window: str | None = None) -> PlanQuotaLimit | None:
        name = str(dimension or "").strip()
        if not name:
            raise ValueError("dimension is required")
        normalized_window = None if window is None else str(window).strip().lower()
        for item in self.quota_limits:
            normalized = item.normalized_copy()
            if normalized.dimension != name:
                continue
            if normalized_window is None or normalized.window == normalized_window:
                return normalized
        return None

    def rate_for(self, meter_key: str) -> PlanRateCardItem | None:
        key = str(meter_key or "").strip()
        if not key:
            raise ValueError("meter_key is required")
        for item in self.rate_card:
            normalized = item.normalized_copy()
            if normalized.meter_key == key:
                return normalized
        return None

    def feature_enabled(self, feature_name: str, *, default: bool = False) -> bool:
        name = str(feature_name or "").strip()
        if not name:
            raise ValueError("feature_name is required")
        return bool(self.features.get(name, default))


@dataclass(frozen=True)
class BillingPlanBinding:
    tenant_id: str
    plan_id: TenantPlan
    bound_at: datetime = field(default_factory=utc_now)
    effective_from: datetime = field(default_factory=utc_now)
    overrides: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        from core.tenancy.normalization import require_tenant_id

        require_tenant_id(self.tenant_id)
        if not isinstance(self.plan_id, TenantPlan):
            raise ValueError("plan_id must be a TenantPlan")
        if self.bound_at.tzinfo is None:
            raise ValueError("bound_at must be timezone-aware")
        if self.effective_from.tzinfo is None:
            raise ValueError("effective_from must be timezone-aware")

    def normalized_copy(self) -> "BillingPlanBinding":
        from core.tenancy.normalization import require_tenant_id

        self.validate()
        return replace(
            self,
            tenant_id=require_tenant_id(self.tenant_id),
            overrides=dict(self.overrides),
        )


class TenantPlanStoreContract(Protocol):
    def get_binding(self, tenant_id: str) -> BillingPlanBinding | None: ...
    def save_binding(self, binding: BillingPlanBinding) -> BillingPlanBinding: ...
    def get_plan(self, tenant_id: str) -> BillingPlanSpec | None: ...
    def get_plan_by_id(self, plan_id: TenantPlan) -> BillingPlanSpec | None: ...
    def save_plan(self, plan: BillingPlanSpec) -> BillingPlanSpec: ...


__all__ = [
    "BillingMeterKey",
    "BillingPlanBinding",
    "BillingPlanSpec",
    "CANON_BILLING_PLAN_CONTRACT",
    "PlanQuotaLimit",
    "PlanRateCardItem",
    "TenantPlanStoreContract",
]
