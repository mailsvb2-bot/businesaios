from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from advisory.revenue_os.contracts import RevenueDecisionIntent, RevenueExperiment, RevenueExperimentArm

CANON_ADVISORY_REVENUE_OS_EXPERIMENT_ENGINE = True


@dataclass(frozen=True, slots=True)
class ExperimentRecommendation:
    experiment: RevenueExperiment
    dedup_key: str


class RevenueExperimentEngine:
    def build(
        self,
        *,
        tenant_id: str,
        product_id: str,
        intents: Iterable[RevenueDecisionIntent],
    ) -> tuple[ExperimentRecommendation, ...]:
        normalized = tuple(item.normalized_copy() for item in intents)
        recommendations: list[ExperimentRecommendation] = []
        seen: set[str] = set()
        for intent in normalized:
            if intent.action_type == 'revenue.pricing.recommendation':
                dedup_key = f'{tenant_id}:{product_id}:pricing:{intent.payload.get("plan_id")}'
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                control = RevenueExperimentArm(
                    arm_id='control',
                    label='control',
                    allocation=0.45,
                    intent=RevenueDecisionIntent(
                        action_type='revenue.pricing.control',
                        intent_kind='control',
                        confidence=1.0,
                        payload={'plan_id': intent.payload.get('plan_id')},
                        evidence={'source': 'experiment_engine'},
                        reason_codes=('control_arm',),
                    ),
                )
                treatment = RevenueExperimentArm(
                    arm_id='treatment',
                    label='treatment',
                    allocation=0.45,
                    intent=intent,
                )
                experiment = RevenueExperiment(
                    experiment_id=dedup_key.replace(':', '__'),
                    kind='pricing',
                    hypothesis='bounded price recommendation improves net revenue without harming retention',
                    metric_primary='net_revenue',
                    metric_guardrails=('churn_rate', 'refund_rate', 'conversion_rate'),
                    arms=(control, treatment),
                    holdout_allocation=0.10,
                    max_daily_exposure=5000,
                    metadata={'tenant_id': tenant_id, 'product_id': product_id},
                ).normalized_copy()
                recommendations.append(ExperimentRecommendation(experiment=experiment, dedup_key=dedup_key))
        return tuple(recommendations)


__all__ = ['CANON_ADVISORY_REVENUE_OS_EXPERIMENT_ENGINE', 'ExperimentRecommendation', 'RevenueExperimentEngine']
