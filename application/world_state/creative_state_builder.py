from __future__ import annotations

from config.creative_portfolio_policy import (
    DEFAULT_CREATIVE_STATE_BUILDER_POLICY,
    CreativeStateBuilderPolicy,
)
from core.creative_intelligence.models import CreativeIntelligenceSnapshot


def build_creative_state(
    snapshots: tuple[CreativeIntelligenceSnapshot, ...],
    policy: CreativeStateBuilderPolicy = DEFAULT_CREATIVE_STATE_BUILDER_POLICY,
) -> dict[str, float]:
    if not snapshots:
        return {
            "creative_count": float(policy.zero_value),
            "top_expected_value_score": float(policy.zero_value),
            "top_downside_envelope": float(policy.zero_value),
            "top_rollout_readiness": float(policy.zero_value),
        }

    top = snapshots[0]
    return {
        "creative_count": float(len(snapshots)),
        "top_expected_value_score": float(top.expected_value_score),
        "top_downside_envelope": float(top.downside_envelope),
        "top_rollout_readiness": float(top.experiment_confidence.rollout_readiness),
        "top_incrementality_confidence": float(top.incrementality.confidence_score),
        "top_portfolio_rank_score": float(top.portfolio_rank_score),
    }
