from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime
from math import isfinite
from typing import Any, Protocol

from billing.commercial_cycle_contract import require_aware_datetime
from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_contract import TenantPlan, utc_now

CANON_BILLING_PLAN_CONTRACT = True


def _require_text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _require_number(name: str, value: Any, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or type(value) not in {int, float}:
        raise ValueError(f"{name} must be a finite number")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{name} must be a finite number")
    if normalized < minimum:
        raise ValueError(f"{name} must be >= {minimum:g}")
    return normalized


def _require_mapping(name: str, value: Any) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


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
        _require_text("dimension", self.dimension)
        _require_text("window", self.window)
        _require_number("limit", self.limit)
        if not isinstance(self.hard_stop, bool):
            raise ValueError("hard_stop must be a boolean")
        _require_mapping("metadata", self.metadata)

    def normalized_copy(self) -> PlanQuotaLimit:
        self.validate()
        return replace(
            self,
            dimension=self.dimension.strip(),
            window=self.window.strip().lower(),
            limit=_require_number("limit", self.limit),
            metadata=deepcopy(dict(self.metadata)),
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
        _require_text("meter_key", self.meter_key)
        _require_text("currency", self.currency)
        _require_text("unit_name", self.unit_name)
        _require_number("unit_price", self.unit_price)
        _require_number("included_units", self.included_units)
        _require_mapping("metadata", self.metadata)

    def normalized_copy(self) -> PlanRateCardItem:
        self.validate()
        return replace(
            self,
            meter_key=self.meter_key.strip(),
            unit_price=_require_number("unit_price", self.unit_price),
            currency=self.currency.strip().upper(),
            unit_name=self.unit_name.strip(),
            included_units=_require_number("included_units", self.included_units),
            metadata=deepcopy(dict(self.metadata)),
        )

    def billable_units(self, quantity: float) -> float:
        normalized = self.normalized_copy()
        requested = _require_number("quantity", quantity)
        return max(0.0, requested - normalized.included_units)

    def charge_for(self, quantity: float) -> float:
        normalized = self.normalized_copy()
        return round(normalized.billable_units(quantity) * normalized.unit_price, 6)


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
        _require_text("display_name", self.display_name)
        _require_text("version", self.version)
        require_aware_datetime("created_at", self.created_at)
        if not isinstance(self.quota_limits, tuple):
            raise ValueError("quota_limits must be a tuple")
        if not isinstance(self.rate_card, tuple):
            raise ValueError("rate_card must be a tuple")
        features = _require_mapping("features", self.features)
        _require_mapping("metadata", self.metadata)

        seen_quota_keys: set[tuple[str, str]] = set()
        seen_meters: set[str] = set()
        for quota in self.quota_limits:
            if not isinstance(quota, PlanQuotaLimit):
                raise ValueError("quota_limits must contain PlanQuotaLimit values")
            normalized = quota.normalized_copy()
            quota_key = (normalized.dimension, normalized.window)
            if quota_key in seen_quota_keys:
                raise ValueError(f"duplicate plan quota: {quota_key}")
            seen_quota_keys.add(quota_key)
        for item in self.rate_card:
            if not isinstance(item, PlanRateCardItem):
                raise ValueError("rate_card must contain PlanRateCardItem values")
            normalized_item = item.normalized_copy()
            if normalized_item.meter_key in seen_meters:
                raise ValueError(f"duplicate rate card meter: {normalized_item.meter_key}")
            seen_meters.add(normalized_item.meter_key)

        normalized_feature_names: set[str] = set()
        for key, enabled in features.items():
            name = _require_text("feature name", key)
            if name in normalized_feature_names:
                raise ValueError(f"duplicate feature name: {name}")
            normalized_feature_names.add(name)
            if not isinstance(enabled, bool):
                raise ValueError("feature flags must be booleans")

    def normalized_copy(self) -> BillingPlanSpec:
        self.validate()
        return replace(
            self,
            display_name=self.display_name.strip(),
            version=self.version.strip(),
            quota_limits=tuple(item.normalized_copy() for item in self.quota_limits),
            rate_card=tuple(item.normalized_copy() for item in self.rate_card),
            features={key.strip(): value for key, value in self.features.items()},
            metadata=deepcopy(dict(self.metadata)),
        )

    def quota_for(self, dimension: str, *, window: str | None = None) -> PlanQuotaLimit | None:
        name = _require_text("dimension", dimension)
        normalized_window = None if window is None else _require_text("window", window).lower()
        for item in self.quota_limits:
            normalized = item.normalized_copy()
            if normalized.dimension != name:
                continue
            if normalized_window is None or normalized.window == normalized_window:
                return normalized
        return None

    def rate_for(self, meter_key: str) -> PlanRateCardItem | None:
        key = _require_text("meter_key", meter_key)
        for item in self.rate_card:
            normalized = item.normalized_copy()
            if normalized.meter_key == key:
                return normalized
        return None

    def feature_enabled(self, feature_name: str, *, default: bool = False) -> bool:
        name = _require_text("feature_name", feature_name)
        if not isinstance(default, bool):
            raise ValueError("default must be a boolean")
        enabled = self.features.get(name, default)
        if not isinstance(enabled, bool):
            raise ValueError("feature flags must be booleans")
        return enabled


@dataclass(frozen=True)
class BillingPlanBinding:
    tenant_id: str
    plan_id: TenantPlan
    bound_at: datetime = field(default_factory=utc_now)
    effective_from: datetime = field(default_factory=utc_now)
    overrides: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not isinstance(self.tenant_id, str):
            raise ValueError("tenant_id must be a string")
        require_tenant_id(self.tenant_id)
        if not isinstance(self.plan_id, TenantPlan):
            raise ValueError("plan_id must be a TenantPlan")
        require_aware_datetime("bound_at", self.bound_at)
        require_aware_datetime("effective_from", self.effective_from)
        _require_mapping("overrides", self.overrides)

    def normalized_copy(self) -> BillingPlanBinding:
        self.validate()
        return replace(
            self,
            tenant_id=require_tenant_id(self.tenant_id),
            overrides=deepcopy(dict(self.overrides)),
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
