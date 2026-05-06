from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from billing.plan_contract import BillingPlanSpec
from runtime.monetization import MonetizationPlan
from runtime.monetization import MonetizationService
from runtime.monetization import TaxContext
from runtime.monetization import UsageInvoiceRequest

CANON_BILLING_MONETIZATION_ADAPTER = True


@dataclass(frozen=True, slots=True)
class BillingMonetizationAdapter:
    """Boundary adapter from legacy billing plan specs to canonical runtime monetization.

    No second billing brain here: it only translates existing canonical billing
    data into the runtime monetization owner surface.
    """

    def plan_from_spec(self, plan: BillingPlanSpec) -> MonetizationPlan:
        normalized = plan.normalized_copy()
        first_rate = normalized.rate_card[0] if normalized.rate_card else None
        currency = first_rate.currency if first_rate is not None else 'USD'
        included_usage = {item.meter_key: item.included_units for item in normalized.rate_card}
        base_amount_minor = int(round(float(normalized.metadata.get('base_amount', 0.0)) * 100))
        included_seats = int(normalized.metadata.get('included_seats', 0) or 0)
        return MonetizationPlan(
            plan_id=normalized.plan_id.value,
            display_name=normalized.display_name,
            currency=currency,
            interval=str(normalized.metadata.get('interval', 'monthly')),
            amount_minor=base_amount_minor,
            included_usage=included_usage,
            included_seats=included_seats,
            metadata=dict(normalized.metadata),
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
        country_code: str = 'US',
        is_business_customer: bool = False,
        tax_id: str | None = None,
        subscription_id: str | None = None,
    ):
        runtime_plan = self.plan_from_spec(plan)
        service.register_plan(runtime_plan)
        return service.build_usage_invoice(
            UsageInvoiceRequest(
                tenant_id=tenant_id,
                user_id=user_id,
                plan_id=runtime_plan.plan_id,
                metered_usage=dict(metered_usage),
                seat_count=seat_count,
                tax_context=TaxContext(country_code=country_code, is_business_customer=is_business_customer, tax_id=tax_id),
                meter_prices=dict(meter_prices or {}),
                seat_price=float(seat_price),
                subscription_id=subscription_id,
            )
        )


__all__ = ['BillingMonetizationAdapter', 'CANON_BILLING_MONETIZATION_ADAPTER']
