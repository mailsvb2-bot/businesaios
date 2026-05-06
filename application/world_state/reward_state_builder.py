from __future__ import annotations

from contracts.decisioning.reward_signal_contract import RewardSignalContract


def build_reward_state(signal: RewardSignalContract) -> dict[str, float]:
    return {
        "immediate_reward": float(signal.immediate_reward),
        "expected_future_value": float(signal.expected_future_value),
        "risk_cost": float(signal.risk_cost),
        "uncertainty_penalty": float(signal.uncertainty_penalty),
        "constraint_cost": float(signal.constraint_cost),
        "scalarized_value": float(signal.scalarized_value()),
    }
