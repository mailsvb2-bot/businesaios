from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RewardSignalContract:
    immediate_reward: float
    expected_future_value: float
    risk_cost: float
    uncertainty_penalty: float = 0.0
    constraint_cost: float = 0.0

    def scalarized_value(self) -> float:
        return (
            float(self.immediate_reward)
            + float(self.expected_future_value)
            - float(self.risk_cost)
            - float(self.uncertainty_penalty)
            - float(self.constraint_cost)
        )
