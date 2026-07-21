from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from math import isfinite
from typing import Any

from billing.commercial_cycle_contract import require_aware_datetime
from billing.plan_contract import BillingPlanSpec
from runtime.monetization import RevenuePaywallVariantInput
from runtime.monetization import RevenuePlanInput
from runtime.monetization import RevenuePricePointInput
from runtime.monetization import RevenueSnapshotInput

CANON_BILLING_REVENUE_OS_BRIDGE = True

_BILLING_DAYS = {"weekly": 7, "monthly": 30, "yearly": 365}


def _require_text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


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


def _require_finite_number(name: str, value: Any, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or type(value) not in {int, float}:
        raise ValueError(f"{name} must be a finite number")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{name} must be a finite number")
    if minimum is not None and normalized < minimum:
        raise ValueError(f"{name} must be >= {minimum:g}")
    return normalized



def _require_money_amount(name: str, value: Any) -> float:
    amount = _require_finite_number(name, value, minimum=0.0)
    minor = Decimal(str(value)) * Decimal("100")
    if minor != minor.to_integral_value():
        raise ValueError(f"{name} must have cent precision")
    return amount


def _require_interval(value: Any) -> str:
    interval = _require_text("interval", value).lower()
    if interval not in _BILLING_DAYS:
        raise ValueError("interval must be weekly, monthly, or yearly")
    return interval


def _normalized_plans(plans: Iterable[BillingPlanSpec]) -> tuple[BillingPlanSpec, ...]:
    if isinstance(plans, (str, bytes, Mapping)):
        raise ValueError("plans must be an iterable of BillingPlanSpec values")
    try:
        iterator = iter(plans)
    except TypeError as exc:
        raise ValueError("plans must be an iterable of BillingPlanSpec values") from exc
    normalized: list[BillingPlanSpec] = []
    for plan in iterator:
        if not isinstance(plan, BillingPlanSpec):
            raise ValueError("plans must contain BillingPlanSpec values")
        normalized.append(plan.normalized_copy())
    if not normalized:
        raise ValueError("at least one plan is required")
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class BillingRevenueOSBridge:
    """Translate canonical billing state into passive Revenue OS inputs."""

    def subscription_plan_from_spec(self, plan: BillingPlanSpec) -> RevenuePlanInput:
        if not isinstance(plan, BillingPlanSpec):
            raise ValueError("plan must be a BillingPlanSpec")
        normalized = plan.normalized_copy()
        first_rate = normalized.rate_card[0] if normalized.rate_card else None
        currency = first_rate.currency if first_rate is not None else "USD"
        metadata = normalized.metadata
        interval = _require_interval(metadata.get("interval", "monthly"))
        return RevenuePlanInput(
            plan_id=normalized.plan_id.value,
            tier=_require_text("tier", metadata.get("tier", normalized.plan_id.value)).lower(),
            price=RevenuePricePointInput(
                product_id=normalized.plan_id.value,
                currency=currency,
                amount=_require_money_amount("base_amount", metadata.get("base_amount", 0.0)),
                billing_period_days=_BILLING_DAYS[interval],
                trial_days=_require_nonnegative_int("trial_days", metadata.get("trial_days", 0)),
                source="billing.plan_contract",
                metadata={"display_name": normalized.display_name, "version": normalized.version},
            ),
            feature_flags=tuple(sorted(name for name, enabled in normalized.features.items() if enabled)),
            seats_included=_require_nonnegative_int("included_seats", metadata.get("included_seats", 1)),
            recommended=_require_bool("recommended", metadata.get("recommended", False)),
        )

    def default_paywall_variants(self, plans: Iterable[BillingPlanSpec]) -> tuple[RevenuePaywallVariantInput, ...]:
        normalized = _normalized_plans(plans)
        has_trial = any(
            _require_nonnegative_int("trial_days", plan.metadata.get("trial_days", 0)) > 0
            for plan in normalized
        )
        return (
            RevenuePaywallVariantInput(
                variant_id="value-anchor",
                headline="Best value for growing teams",
                theme="default",
                emphasizes_trial=has_trial,
                social_proof_density=0.55,
                friction_score=0.35,
                metadata={"owner": "billing.revenue_os_bridge"},
            ),
            RevenuePaywallVariantInput(
                variant_id="low-friction",
                headline="Start safely and upgrade later",
                theme="calm",
                emphasizes_trial=has_trial,
                social_proof_density=0.25,
                friction_score=0.15,
                metadata={"owner": "billing.revenue_os_bridge"},
            ),
        )

    def revenue_snapshot_from_metrics(
        self,
        *,
        observed_at: datetime,
        visitors: int,
        trials_started: int,
        conversions: int,
        retained_subscribers: int,
        churned_subscribers: int,
        refunds: int,
        gross_revenue: float,
        net_revenue: float,
        acquisition_spend: float,
        active_subscribers: int,
        trial_subscribers: int = 0,
    ) -> RevenueSnapshotInput:
        require_aware_datetime("observed_at", observed_at)
        return RevenueSnapshotInput(
            observed_at=observed_at,
            visitors=_require_nonnegative_int("visitors", visitors),
            trials_started=_require_nonnegative_int("trials_started", trials_started),
            conversions=_require_nonnegative_int("conversions", conversions),
            retained_subscribers=_require_nonnegative_int("retained_subscribers", retained_subscribers),
            churned_subscribers=_require_nonnegative_int("churned_subscribers", churned_subscribers),
            refunds=_require_nonnegative_int("refunds", refunds),
            gross_revenue=_require_finite_number("gross_revenue", gross_revenue, minimum=0.0),
            net_revenue=_require_finite_number("net_revenue", net_revenue),
            acquisition_spend=_require_finite_number("acquisition_spend", acquisition_spend, minimum=0.0),
            active_subscribers=_require_nonnegative_int("active_subscribers", active_subscribers),
            trial_subscribers=_require_nonnegative_int("trial_subscribers", trial_subscribers),
        )


__all__ = ["BillingRevenueOSBridge", "CANON_BILLING_REVENUE_OS_BRIDGE"]
