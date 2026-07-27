from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from billing.money import (
    decimal_to_minor_units,
    legacy_float,
    money_decimal,
    ratio_decimal,
)
from billing.plan_contract import BillingPlanSpec
from billing.subscription_lifecycle import SubscriptionLifecycleService


CANON_BILLING_PLAN_CHANGE_POLICY = True


@dataclass(frozen=True)
class PlanChangeQuote:
    from_plan_id: str
    to_plan_id: str
    proration_fraction: float
    delta_minor: int
    currency: str
    effective_immediately: bool
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.from_plan_id or "").strip():
            raise ValueError("from_plan_id is required")
        if not str(self.to_plan_id or "").strip():
            raise ValueError("to_plan_id is required")
        ratio_decimal(self.proration_fraction, name="proration_fraction")
        if not str(self.currency or "").strip():
            raise ValueError("currency is required")
        if isinstance(self.delta_minor, bool) or not isinstance(self.delta_minor, int):
            raise ValueError("delta_minor must be an integer")


class PlanChangePolicy:
    def __init__(self, *, lifecycle: SubscriptionLifecycleService | None = None) -> None:
        self._lifecycle = lifecycle or SubscriptionLifecycleService()

    def quote(
        self,
        *,
        current_plan: BillingPlanSpec,
        next_plan: BillingPlanSpec,
        changed_at: datetime,
        cycle,
        effective_immediately: bool = True,
    ) -> PlanChangeQuote:
        current_spec = current_plan.normalized_copy()
        next_spec = next_plan.normalized_copy()
        cycle.validate()
        if changed_at.tzinfo is None:
            raise ValueError("changed_at must be timezone-aware")
        raw_fraction = (
            self._lifecycle.plan_change_proration_fraction(
                cycle=cycle,
                changed_at=changed_at,
            )
            if effective_immediately
            else 0
        )
        fraction = ratio_decimal(raw_fraction, name="proration_fraction")
        current_base = money_decimal(
            current_spec.metadata.get("base_amount", 0) or 0,
            name="current_base_amount",
        )
        next_base = money_decimal(
            next_spec.metadata.get("base_amount", 0) or 0,
            name="next_base_amount",
        )
        current_rate = current_spec.rate_card[0] if current_spec.rate_card else None
        next_rate = next_spec.rate_card[0] if next_spec.rate_card else None
        current_currency = (
            current_rate.currency
            if current_rate is not None
            else str(current_spec.metadata.get("currency", "USD"))
        )
        next_currency = (
            next_rate.currency
            if next_rate is not None
            else str(next_spec.metadata.get("currency", current_currency))
        )
        if str(current_currency).upper() != str(next_currency).upper():
            raise ValueError("cross-currency plan changes require external FX handling")
        delta_minor = decimal_to_minor_units(
            (next_base - current_base) * fraction,
            name="prorated_plan_delta",
            allow_negative=True,
        )
        quote = PlanChangeQuote(
            from_plan_id=current_spec.plan_id.value,
            to_plan_id=next_spec.plan_id.value,
            proration_fraction=legacy_float(fraction, name="proration_fraction"),
            delta_minor=delta_minor,
            currency=str(next_currency).upper(),
            effective_immediately=bool(effective_immediately),
            metadata={
                "owner": "billing.plan_change_policy",
                "cycle_start_at": cycle.start_at.isoformat(),
                "cycle_end_at": cycle.end_at.isoformat(),
                "current_base_amount": legacy_float(
                    current_base,
                    name="current_base_amount",
                ),
                "next_base_amount": legacy_float(
                    next_base,
                    name="next_base_amount",
                ),
            },
        )
        quote.validate()
        return quote


__all__ = ["CANON_BILLING_PLAN_CHANGE_POLICY", "PlanChangePolicy", "PlanChangeQuote"]
