from __future__ import annotations

from config.risk_evaluation_policy import DEFAULT_RISK_COST_POLICY, RiskCostPolicy


def build_risk_cost(
    *,
    downside_envelope: float,
    architecture_instability: float,
    blast_radius_risk: float,
    flow_turbulence: float,
    policy: RiskCostPolicy = DEFAULT_RISK_COST_POLICY,
) -> float:
    return max(
        float(policy.minimum_score),
        min(
            float(policy.maximum_score),
            (float(policy.downside_envelope_weight) * float(downside_envelope))
            + (float(policy.architecture_instability_weight) * float(architecture_instability))
            + (float(policy.blast_radius_risk_weight) * float(blast_radius_risk))
            + (float(policy.flow_turbulence_weight) * float(flow_turbulence)),
        ),
    )
