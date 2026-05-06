from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

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
        if not str(self.from_plan_id or '').strip():
            raise ValueError('from_plan_id is required')
        if not str(self.to_plan_id or '').strip():
            raise ValueError('to_plan_id is required')
        if not 0.0 <= float(self.proration_fraction) <= 1.0:
            raise ValueError('proration_fraction must be between 0 and 1')
        if not str(self.currency or '').strip():
            raise ValueError('currency is required')


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
            raise ValueError('changed_at must be timezone-aware')
        fraction = self._lifecycle.plan_change_proration_fraction(cycle=cycle, changed_at=changed_at) if effective_immediately else 0.0
        current_base = float(current_spec.metadata.get('base_amount', 0.0) or 0.0)
        next_base = float(next_spec.metadata.get('base_amount', 0.0) or 0.0)
        current_rate = current_spec.rate_card[0] if current_spec.rate_card else None
        next_rate = next_spec.rate_card[0] if next_spec.rate_card else None
        current_currency = current_rate.currency if current_rate is not None else str(current_spec.metadata.get('currency', 'USD'))
        next_currency = next_rate.currency if next_rate is not None else str(next_spec.metadata.get('currency', current_currency))
        if str(current_currency).upper() != str(next_currency).upper():
            raise ValueError('cross-currency plan changes require external FX handling')
        delta_minor = int(round((next_base - current_base) * fraction * 100))
        quote = PlanChangeQuote(
            from_plan_id=current_spec.plan_id.value,
            to_plan_id=next_spec.plan_id.value,
            proration_fraction=fraction,
            delta_minor=delta_minor,
            currency=str(next_currency).upper(),
            effective_immediately=bool(effective_immediately),
            metadata={
                'owner': 'billing.plan_change_policy',
                'cycle_start_at': cycle.start_at.isoformat(),
                'cycle_end_at': cycle.end_at.isoformat(),
                'current_base_amount': current_base,
                'next_base_amount': next_base,
            },
        )
        quote.validate()
        return quote


__all__ = ['CANON_BILLING_PLAN_CHANGE_POLICY', 'PlanChangePolicy', 'PlanChangeQuote']
