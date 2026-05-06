from __future__ import annotations

from dataclasses import dataclass

from advisory.revenue_os.churn_model import ChurnProjection
from advisory.revenue_os.contracts import RevenueDecisionIntent, RevenueSnapshot, SubscriptionPlan
from advisory.revenue_os.ltv_model import LTVProjection
from advisory.revenue_os.pricing_policy import PricingPolicy

CANON_ADVISORY_REVENUE_OS_PRICING_ENGINE = True


@dataclass(frozen=True, slots=True)
class PricingRecommendation:
    plan_id: str
    current_amount: float
    suggested_amount: float
    change_pct: float
    confidence: float
    requires_approval: bool
    reason_codes: tuple[str, ...]

    def to_intent(self) -> RevenueDecisionIntent:
        blast_radius = 'high' if self.requires_approval else 'moderate'
        return RevenueDecisionIntent(
            action_type='revenue.pricing.recommendation',
            intent_kind='advisory',
            confidence=self.confidence,
            payload={
                'plan_id': self.plan_id,
                'current_amount': self.current_amount,
                'suggested_amount': self.suggested_amount,
                'change_pct': self.change_pct,
            },
            evidence={'reason_codes': list(self.reason_codes)},
            reason_codes=self.reason_codes,
            blast_radius=blast_radius,
            requires_approval=self.requires_approval,
        )


class RevenuePricingEngine:
    def __init__(self, *, policy: PricingPolicy | None = None) -> None:
        self._policy = policy or PricingPolicy()

    def recommend(
        self,
        *,
        plan: SubscriptionPlan,
        latest_snapshot: RevenueSnapshot,
        ltv: LTVProjection,
        churn: ChurnProjection,
    ) -> PricingRecommendation:
        normalized_plan = plan.normalized_copy()
        snapshot = latest_snapshot.normalized_copy()
        desired_change_pct = 0.0
        reason_codes: list[str] = []
        if ltv.predicted_ltv > 0 and snapshot.conversions > 0:
            observed_cac = snapshot.acquisition_spend / snapshot.conversions if snapshot.conversions else 0.0
            ratio = 0.0 if observed_cac <= 0 else ltv.predicted_ltv / observed_cac
            if ratio >= 3.0 and churn.risk_band == 'stable' and snapshot.contribution_margin >= self._policy.minimum_margin:
                desired_change_pct = 0.08
                reason_codes.append('ltv_to_cac_strong')
            elif ratio < 1.5 or churn.risk_band == 'critical':
                if self._policy.allow_price_drop_when_churn_critical:
                    desired_change_pct = -0.10
                    reason_codes.append('retention_pressure')
        if snapshot.refund_rate >= 0.08:
            desired_change_pct = min(desired_change_pct, -0.05)
            reason_codes.append('refund_pressure')
        multiplier = self._policy.bounded_multiplier(desired_change_pct=desired_change_pct)
        current_amount = normalized_plan.price.amount
        suggested_amount = round(current_amount * multiplier, 6)
        change_pct = round((suggested_amount / current_amount) - 1.0, 6) if current_amount > 0 else 0.0
        requires_approval = abs(change_pct) >= self._policy.require_approval_above_pct
        confidence = round(min(0.95, (ltv.confidence + churn.evidence_strength) / 2.0), 6)
        if not reason_codes:
            reason_codes.append('hold_price')
        return PricingRecommendation(
            plan_id=normalized_plan.plan_id,
            current_amount=current_amount,
            suggested_amount=suggested_amount,
            change_pct=change_pct,
            confidence=confidence,
            requires_approval=requires_approval,
            reason_codes=tuple(sorted(set(reason_codes))),
        )


__all__ = ['CANON_ADVISORY_REVENUE_OS_PRICING_ENGINE', 'PricingRecommendation', 'RevenuePricingEngine']
