from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from billing.plan_contract import BillingPlanSpec
from runtime.monetization import (
    RevenuePaywallVariantInput,
    RevenuePlanInput,
    RevenuePricePointInput,
    RevenueSnapshotInput,
)

CANON_BILLING_REVENUE_OS_BRIDGE = True


@dataclass(frozen=True, slots=True)
class BillingRevenueOSBridge:
    """Boundary translator from canonical billing surfaces to runtime revenue inputs.

    This bridge is translation-only. It must not execute actions or become a
    second commercial owner.
    """

    def subscription_plan_from_spec(self, plan: BillingPlanSpec) -> RevenuePlanInput:
        normalized = plan.normalized_copy()
        first_rate = normalized.rate_card[0] if normalized.rate_card else None
        currency = first_rate.currency if first_rate is not None else 'USD'
        base_amount = float(normalized.metadata.get('base_amount', 0.0) or 0.0)
        interval = str(normalized.metadata.get('interval', 'monthly')).strip().lower()
        billing_days = 365 if interval == 'yearly' else 30
        trial_days = int(normalized.metadata.get('trial_days', 0) or 0)
        tier = str(normalized.metadata.get('tier', normalized.plan_id.value)).strip().lower()
        recommended = bool(normalized.metadata.get('recommended', False))
        return RevenuePlanInput(
            plan_id=normalized.plan_id.value,
            tier=tier,
            price=RevenuePricePointInput(
                product_id=normalized.plan_id.value,
                currency=currency,
                amount=base_amount,
                billing_period_days=billing_days,
                trial_days=trial_days,
                source='billing.plan_contract',
                metadata={'display_name': normalized.display_name, 'version': normalized.version},
            ),
            feature_flags=tuple(sorted(name for name, enabled in normalized.features.items() if enabled)),
            seats_included=int(normalized.metadata.get('included_seats', 1) or 1),
            recommended=recommended,
        )

    def default_paywall_variants(self, plans: Iterable[BillingPlanSpec]) -> tuple[RevenuePaywallVariantInput, ...]:
        normalized = tuple(plan.normalized_copy() for plan in plans)
        if not normalized:
            raise ValueError('at least one plan is required')
        has_trial = any(int(plan.metadata.get('trial_days', 0) or 0) > 0 for plan in normalized)
        return (
            RevenuePaywallVariantInput(
                variant_id='value-anchor',
                headline='Best value for growing teams',
                theme='default',
                emphasizes_trial=has_trial,
                social_proof_density=0.55,
                friction_score=0.35,
                metadata={'owner': 'billing.revenue_os_bridge'},
            ),
            RevenuePaywallVariantInput(
                variant_id='low-friction',
                headline='Start safely and upgrade later',
                theme='calm',
                emphasizes_trial=has_trial,
                social_proof_density=0.25,
                friction_score=0.15,
                metadata={'owner': 'billing.revenue_os_bridge'},
            ),
        )

    def revenue_snapshot_from_metrics(
        self,
        *,
        observed_at,
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
        return RevenueSnapshotInput(
            observed_at=observed_at,
            visitors=int(visitors),
            trials_started=int(trials_started),
            conversions=int(conversions),
            retained_subscribers=int(retained_subscribers),
            churned_subscribers=int(churned_subscribers),
            refunds=int(refunds),
            gross_revenue=float(gross_revenue),
            net_revenue=float(net_revenue),
            acquisition_spend=float(acquisition_spend),
            active_subscribers=int(active_subscribers),
            trial_subscribers=int(trial_subscribers),
        )


__all__ = ['BillingRevenueOSBridge', 'CANON_BILLING_REVENUE_OS_BRIDGE']
