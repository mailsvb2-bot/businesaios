from __future__ import annotations

from config.creative_portfolio_policy import DEFAULT_PORTFOLIO_SCORING_POLICY, PortfolioScoringPolicy
from core.creative_intelligence.models import CreativeIntelligenceSnapshot


def portfolio_rank_score(
    snapshot: CreativeIntelligenceSnapshot,
    policy: PortfolioScoringPolicy = DEFAULT_PORTFOLIO_SCORING_POLICY,
) -> float:
    score = (
        float(policy.expected_value_weight) * snapshot.expected_value_score
        + float(policy.rollout_readiness_weight) * snapshot.experiment_confidence.rollout_readiness
        + float(policy.incrementality_confidence_weight) * snapshot.incrementality.confidence_score
        - float(policy.downside_penalty_weight) * snapshot.downside_envelope
    )
    return max(float(policy.score_floor), min(float(policy.score_ceiling), score))


def rank_portfolio(
    snapshots: tuple[CreativeIntelligenceSnapshot, ...],
) -> tuple[CreativeIntelligenceSnapshot, ...]:
    return tuple(
        sorted(
            snapshots,
            key=lambda item: portfolio_rank_score(item),
            reverse=True,
        )
    )
