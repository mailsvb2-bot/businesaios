from __future__ import annotations

from config.creative_expected_value_policy import (
    DEFAULT_CREATIVE_EXPECTED_VALUE_POLICY,
    CreativeExpectedValuePolicy,
)
from core.creative_intelligence.models import (
    CreativeEconomicsInput,
    CreativePnLSnapshot,
    ExperimentConfidenceSnapshot,
    IncrementalitySnapshot,
)


def expected_value_score(
    *,
    item: CreativeEconomicsInput,
    pnl: CreativePnLSnapshot,
    incrementality: IncrementalitySnapshot,
    confidence: ExperimentConfidenceSnapshot,
    policy: CreativeExpectedValuePolicy = DEFAULT_CREATIVE_EXPECTED_VALUE_POLICY,
) -> float:
    score = (
        float(policy.roi_weight) * pnl.roi
        + float(policy.contribution_margin_weight) * pnl.contribution_margin_ratio
        + float(policy.incrementality_weight)
        * incrementality.estimated_effect
        * incrementality.confidence_score
        + float(policy.rollout_readiness_weight) * confidence.rollout_readiness
        + float(policy.future_value_weight) * float(item.expected_future_value)
    )
    return max(float(policy.min_score), min(float(policy.max_score), score))
