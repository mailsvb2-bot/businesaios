from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from advisory.revenue_os.churn_model import ChurnProjection
from advisory.revenue_os.contracts import RevenueDecisionIntent, SubscriptionPlan

CANON_ADVISORY_REVENUE_OS_SUBSCRIPTION_ENGINE = True


@dataclass(frozen=True, slots=True)
class SubscriptionRecommendation:
    primary_plan_id: str
    anchor_plan_id: str | None
    confidence: float
    reason_codes: tuple[str, ...]

    def to_intent(self) -> RevenueDecisionIntent:
        return RevenueDecisionIntent(
            action_type='revenue.subscription.recommendation',
            intent_kind='advisory',
            confidence=self.confidence,
            payload={
                'primary_plan_id': self.primary_plan_id,
                'anchor_plan_id': self.anchor_plan_id,
            },
            evidence={'reason_codes': list(self.reason_codes)},
            reason_codes=self.reason_codes,
            blast_radius='moderate',
            requires_approval=False,
        )


class SubscriptionEngine:
    def recommend(self, plans: Sequence[SubscriptionPlan], *, churn: ChurnProjection) -> SubscriptionRecommendation:
        normalized = tuple(item.normalized_copy() for item in plans)
        if not normalized:
            raise ValueError('at least one subscription plan is required')
        primary = max(
            normalized,
            key=lambda item: (
                item.recommended,
                item.tier == 'pro',
                item.seats_included,
                -item.price.amount,
                item.plan_id,
            ),
        )
        anchor = min(normalized, key=lambda item: (item.price.amount, item.plan_id))
        reasons = ['plan_ladder_selected']
        if churn.risk_band != 'stable':
            reasons.append('retention_sensitive_positioning')
        if anchor.tier == 'trial' or anchor.tier == 'free' or anchor.price.amount <= primary.price.amount:
            reasons.append('cheap_anchor_retained')
        return SubscriptionRecommendation(
            primary_plan_id=primary.plan_id,
            anchor_plan_id=anchor.plan_id if anchor.plan_id != primary.plan_id else None,
            confidence=0.72 if churn.risk_band == 'stable' else 0.79,
            reason_codes=tuple(sorted(reasons)),
        )


__all__ = ['CANON_ADVISORY_REVENUE_OS_SUBSCRIPTION_ENGINE', 'SubscriptionEngine', 'SubscriptionRecommendation']
