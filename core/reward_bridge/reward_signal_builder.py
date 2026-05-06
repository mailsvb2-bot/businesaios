from __future__ import annotations

from contracts.decisioning.reward_signal_contract import RewardSignalContract
from core.creative_intelligence.models import CreativeIntelligenceSnapshot
from core.reward_bridge.constraint_cost_builder import build_constraint_cost
from core.reward_bridge.future_value_builder import build_future_value
from core.reward_bridge.immediate_reward_builder import build_immediate_reward
from core.reward_bridge.risk_cost_builder import build_risk_cost
from core.reward_bridge.uncertainty_penalty_builder import build_uncertainty_penalty


def build_reward_signal(
    *,
    snapshot: CreativeIntelligenceSnapshot,
    architecture_global_stability: float,
    blast_radius_risk: float,
    flow_turbulence: float,
    market_competitive_shift: float,
) -> RewardSignalContract:
    return RewardSignalContract(
        immediate_reward=build_immediate_reward(snapshot),
        expected_future_value=build_future_value(snapshot),
        risk_cost=build_risk_cost(
            downside_envelope=snapshot.downside_envelope,
            architecture_instability=max(0.0, min(1.0, 1.0 - architecture_global_stability)),
            blast_radius_risk=blast_radius_risk,
            flow_turbulence=flow_turbulence,
        ),
        uncertainty_penalty=build_uncertainty_penalty(snapshot),
        constraint_cost=build_constraint_cost(
            architecture_global_stability=architecture_global_stability,
            market_competitive_shift=market_competitive_shift,
        ),
    )
