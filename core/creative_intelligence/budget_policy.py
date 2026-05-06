from __future__ import annotations

from config.creative_budget_policy import (
    DEFAULT_CREATIVE_BUDGET_POLICY,
    CreativeBudgetPolicy,
)
from core.creative_intelligence.models import CreativeIntelligenceSnapshot, PortfolioBudgetAdvice


def build_budget_advice(
    *,
    snapshot: CreativeIntelligenceSnapshot,
    total_budget: float,
    policy: CreativeBudgetPolicy = DEFAULT_CREATIVE_BUDGET_POLICY,
) -> PortfolioBudgetAdvice:
    total = max(float(0), float(total_budget))
    strength = max(
        float(0),
        min(
            float(1),
            float(policy.confidence_readiness_weight) * snapshot.experiment_confidence.rollout_readiness
            + float(policy.expected_value_weight) * max(float(0), snapshot.expected_value_score),
        ),
    )
    risk_drag = max(float(0), min(float(1), snapshot.downside_envelope))

    floor_budget = total * max(float(0), float(policy.floor_strength_multiplier) * strength)
    target_budget = total * max(
        float(0),
        (float(policy.target_base_pct) + float(policy.target_strength_multiplier) * strength)
        * (1 - float(policy.target_risk_drag_multiplier) * risk_drag),
    )
    ceiling_budget = total * max(
        float(0),
        (float(policy.ceiling_base_pct) + float(policy.ceiling_strength_multiplier) * strength)
        * (1 - float(policy.ceiling_risk_drag_multiplier) * risk_drag),
    )

    bias = "hold"
    if (
        snapshot.expected_value_score > float(policy.increase_bias_ev_threshold)
        and snapshot.downside_envelope < float(policy.increase_bias_downside_threshold)
    ):
        bias = "increase"
    elif (
        snapshot.expected_value_score < float(policy.decrease_bias_ev_threshold)
        or snapshot.downside_envelope > float(policy.decrease_bias_downside_threshold)
    ):
        bias = "decrease"

    return PortfolioBudgetAdvice(
        creative_id=snapshot.creative_id,
        floor_budget=floor_budget,
        target_budget=target_budget,
        ceiling_budget=max(target_budget, ceiling_budget),
        reallocation_bias=bias,
    )
