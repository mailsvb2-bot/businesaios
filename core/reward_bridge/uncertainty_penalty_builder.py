from __future__ import annotations

from config.risk_evaluation_policy import (
    DEFAULT_UNCERTAINTY_PENALTY_POLICY,
    UncertaintyPenaltyPolicy,
)
from core.creative_intelligence.models import CreativeIntelligenceSnapshot


def build_uncertainty_penalty(
    snapshot: CreativeIntelligenceSnapshot,
    *,
    policy: UncertaintyPenaltyPolicy = DEFAULT_UNCERTAINTY_PENALTY_POLICY,
) -> float:
    causal_gap = max(0.0, 1.0 - float(snapshot.incrementality.confidence_score))
    experiment_gap = max(0.0, 1.0 - float(snapshot.experiment_confidence.confidence_score))
    downside = max(0.0, float(snapshot.downside_envelope))
    score = (
        (float(policy.causal_gap_weight) * causal_gap)
        + (float(policy.experiment_gap_weight) * experiment_gap)
        + (float(policy.downside_weight) * downside)
    )
    return max(float(policy.minimum_score), min(float(policy.maximum_score), score))
