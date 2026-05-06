from __future__ import annotations

from config.creative_downside_policy import (
    DEFAULT_CREATIVE_DOWNSIDE_POLICY,
    CreativeDownsidePolicy,
)
from core.creative_intelligence.models import (
    CreativePnLSnapshot,
    ExperimentConfidenceSnapshot,
    IncrementalitySnapshot,
)


def downside_envelope(
    *,
    pnl: CreativePnLSnapshot,
    incrementality: IncrementalitySnapshot,
    confidence: ExperimentConfidenceSnapshot,
    policy: CreativeDownsidePolicy = DEFAULT_CREATIVE_DOWNSIDE_POLICY,
) -> float:
    zero = float("0")
    pnl_risk = max(zero, -pnl.roi)
    causal_risk = incrementality.downside_risk
    confidence_risk = max(zero, float(policy.confidence_floor) - confidence.confidence_score)
    score = (
        (float(policy.pnl_risk_weight) * pnl_risk)
        + (float(policy.causal_risk_weight) * causal_risk)
        + (float(policy.confidence_risk_weight) * confidence_risk)
    )
    return max(float(policy.min_score), min(float(policy.max_score), score))
