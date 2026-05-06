from __future__ import annotations

from core.creative_intelligence.models import CreativeIntelligenceSnapshot
from config.reward_bridge_policy import DEFAULT_FUTURE_VALUE_POLICY, RewardBridgePolicy


def build_future_value(
    snapshot: CreativeIntelligenceSnapshot,
    *,
    policy: RewardBridgePolicy = DEFAULT_FUTURE_VALUE_POLICY,
) -> float:
    score = (
        policy.primary_weight * float(snapshot.expected_value_score)
        + policy.secondary_weight * float(snapshot.incrementality.estimated_effect) * float(snapshot.incrementality.confidence_score)
        + policy.tertiary_weight * float(snapshot.experiment_confidence.rollout_readiness)
    )
    return max(policy.min_score, min(policy.max_score, score))
