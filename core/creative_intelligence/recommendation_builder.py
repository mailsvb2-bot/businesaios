from __future__ import annotations

from application.decisioning.decision_output_guard import assert_non_decision_payload
from core.creative_intelligence.budget_policy import build_budget_advice
from core.creative_intelligence.models import CreativeIntelligenceSnapshot
from kernel.decisioning.decision_types import RecommendationSet


def build_creative_recommendations(
    *,
    snapshots: tuple[CreativeIntelligenceSnapshot, ...],
    total_budget: float,
) -> RecommendationSet:
    items: list[dict[str, object]] = []
    for snapshot in snapshots:
        budget = build_budget_advice(
            snapshot=snapshot,
            total_budget=total_budget,
        )
        items.append(
            {
                "kind": "creative_advisory",
                "creative_id": snapshot.creative_id,
                "expected_value_score": snapshot.expected_value_score,
                "portfolio_rank_score": snapshot.portfolio_rank_score,
                "downside_envelope": snapshot.downside_envelope,
                "incrementality_effect": snapshot.incrementality.estimated_effect,
                "incrementality_confidence": snapshot.incrementality.confidence_score,
                "experiment_rollout_readiness": snapshot.experiment_confidence.rollout_readiness,
                "recommended_floor_budget": budget.floor_budget,
                "recommended_target_budget": budget.target_budget,
                "recommended_ceiling_budget": budget.ceiling_budget,
                "reallocation_bias": budget.reallocation_bias,
            }
        )
    return assert_non_decision_payload(items)
