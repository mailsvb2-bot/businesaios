from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from advisory.revenue_os.churn_model import ChurnProjection
from advisory.revenue_os.contracts import PaywallVariant, RevenueDecisionIntent

CANON_ADVISORY_REVENUE_OS_PAYWALL_OPTIMIZER = True


@dataclass(frozen=True, slots=True)
class PaywallRecommendation:
    variant_id: str
    confidence: float
    reason_codes: tuple[str, ...]

    def to_intent(self) -> RevenueDecisionIntent:
        return RevenueDecisionIntent(
            action_type='revenue.paywall.recommendation',
            intent_kind='advisory',
            confidence=self.confidence,
            payload={'variant_id': self.variant_id},
            evidence={'reason_codes': list(self.reason_codes)},
            reason_codes=self.reason_codes,
            blast_radius='moderate',
            requires_approval=False,
        )


class PaywallOptimizer:
    def recommend(self, variants: Sequence[PaywallVariant], *, churn: ChurnProjection) -> PaywallRecommendation:
        normalized = tuple(item.normalized_copy() for item in variants)
        if not normalized:
            raise ValueError('at least one paywall variant is required')
        scored = []
        for item in normalized:
            score = 0.0
            if churn.risk_band == 'critical' and item.emphasizes_trial:
                score += 0.40
            score += (1.0 - item.friction_score) * 0.35
            score += item.social_proof_density * 0.25
            scored.append((score, item))
        best = max(scored, key=lambda pair: (pair[0], pair[1].variant_id))[1]
        reasons = ['best_variant_score']
        if churn.risk_band == 'critical' and best.emphasizes_trial:
            reasons.append('trial_emphasis_for_retention_pressure')
        return PaywallRecommendation(
            variant_id=best.variant_id,
            confidence=round(min(0.95, 0.55 + (0.10 if churn.risk_band == 'critical' else 0.0)), 6),
            reason_codes=tuple(sorted(reasons)),
        )


__all__ = ['CANON_ADVISORY_REVENUE_OS_PAYWALL_OPTIMIZER', 'PaywallOptimizer', 'PaywallRecommendation']
