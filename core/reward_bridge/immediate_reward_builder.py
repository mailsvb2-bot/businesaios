from __future__ import annotations

from core.creative_intelligence.models import CreativeIntelligenceSnapshot
from config.reward_bridge_policy import DEFAULT_IMMEDIATE_REWARD_POLICY, RewardBridgePolicy


def build_immediate_reward(
    snapshot: CreativeIntelligenceSnapshot,
    *,
    policy: RewardBridgePolicy = DEFAULT_IMMEDIATE_REWARD_POLICY,
) -> float:
    score = (
        policy.primary_weight * float(snapshot.pnl.roi)
        + policy.secondary_weight * float(snapshot.pnl.contribution_margin_ratio)
        + policy.tertiary_weight * float(snapshot.experiment_confidence.uplift)
    )
    return max(policy.min_score, min(policy.max_score, score))
