from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from math import isfinite
from typing import Any

from billing.plan_contract import BillingPlanSpec
from core.tenancy.normalization import require_tenant_id
from runtime.monetization import MonetizationPlan
from runtime.monetization import MonetizationService
from runtime.monetization import TaxContext
from runtime.monetization import UsageInvoiceRequest

CANON_BILLING_MONETIZATION_ADAPTER = True

_ALLOWED_INTERVALS = frozenset({"weekly", "monthly", "yearly"})


def _require_text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _require_optional_text(name: str, value: Any) -> str | None:
    if value is None:
        return None
    return _require_text(name, value)


def _require_bool(name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _require_nonnegative_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be >= 0")
    return value


def _require_finite_number(name: str, value: Any, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or type(value) not in {int, float}:
        raise ValueError(f"{name} must be a finite number")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{name} must be a finite number")
    if normalized < minimum:
        raise ValueError(f"{name} must be >= {minimum:g}")
    return normalized


def _require_base_amount_minor(value: Any) -> int:
    amount = _require_finite_number("base_amount", value)
    minor = Decimal(str(value)) * Decimal("100")
    if minor != minor.to_integral_value():
        raise ValueError("base_amount must have cent precision")
    return int(minor)


def _require_interval(value: Any) -> str:
    interval = _require_text("interval", value).lower()
    if interval not in _ALLOWED_INTERVALS:
        raise ValueError("interval must be weekly, monthly, or yearly")
    return interval


def _require_metric_mapping(name: str, value: Any) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    normalized: dict[str, float] = {}
    for raw_key, raw_value in value.items():
        key = _require_text(f"{name} key", raw_key)
        if key in normalized:
            raise ValueError(f"duplicate {name} key: {key}")
        normalized[key] = _require_finite_number(f"{name}[{key}]", raw_value)
    return normalized


@dataclass(frozen=True, slots=True)
class BillingMonetizationAdapter:
    """Translate canonical billing plan state into runtime monetization inputs."""

    def plan_from_spec(self, plan: BillingPlanSpec) -> MonetizationPlan:
        if not isinstance(plan, BillingPlanSpec):
            raise ValueError("plan must be a BillingPlanSpec")
        normalized = plan.normalized_copy()
        first_rate = normalized.rate_card[0] if normalized.rate_card else None
        currency = first_rate.currency if first_rate is not None else "USD"
        included_usage = {item.meter_key: item.included_units for item in normalized.rate_card}
        metadata = normalized.metadata
        return MonetizationPlan(
            plan_id=normalized.plan_id.value,
            display_name=normalized.display_name,
            currency=currency,
            interval=_require_interval(metadata.get("interval", "monthly")),
            amount_minor=_require_base_amount_minor(metadata.get("base_amount", 0.0)),
            included_usage=included_usage,
            included_seats=_require_nonnegative_int("included_seats", metadata.get("included_seats", 0)),
            metadata=deepcopy(dict(metadata)),
        )

    def build_usage_invoice(
        self,
        *,
        service: MonetizationService,
        tenant_id: str,
        user_id: str,
        plan: BillingPlanSpec,
        metered_usage: Mapping[str, float],
        seat_count: int = 0,
        meter_prices: Mapping[str, float] | None = None,
        seat_price: float = 0.0,
        country_code: str = "US",
        is_business_customer: bool = False,
        tax_id: str | None = None,
        subscription_id: str | None = None,
    ):
        if not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a string")
        normalized_tenant = require_tenant_id(tenant_id)
        normalized_user = _require_text("user_id", user_id)
        normalized_usage = _require_metric_mapping("metered_usage", metered_usage)
        normalized_prices = _require_metric_mapping("meter_prices", {} if meter_prices is None else meter_prices)
        normalized_seats = _require_nonnegative_int("seat_count", seat_count)
        normalized_seat_price = _require_finite_number("seat_price", seat_price)
        normalized_country = _require_text("country_code", country_code).upper()
        normalized_business = _require_bool("is_business_customer", is_business_customer)
        normalized_tax_id = _require_optional_text("tax_id", tax_id)
        normalized_subscription = _require_optional_text("subscription_id", subscription_id)

        runtime_plan = self.plan_from_spec(plan)
        service.register_plan(runtime_plan)
        return service.build_usage_invoice(
            UsageInvoiceRequest(
                tenant_id=normalized_tenant,
                user_id=normalized_user,
                plan_id=runtime_plan.plan_id,
                metered_usage=normalized_usage,
                seat_count=normalized_seats,
                tax_context=TaxContext(
                    country_code=normalized_country,
                    is_business_customer=normalized_business,
                    tax_id=normalized_tax_id,
                ),
                meter_prices=normalized_prices,
                seat_price=normalized_seat_price,
                subscription_id=normalized_subscription,
            )
        )


__all__ = ["BillingMonetizationAdapter", "CANON_BILLING_MONETIZATION_ADAPTER"]
