from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


class EvolutionRejected(Exception):
    pass


@dataclass(frozen=True)
class PolicyMetrics:
    reward: float
    risk: float
    stability: float
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class EvolutionThresholds:
    min_reward_gain: float = 0.01
    max_risk: float = 0.05
    min_stability: float = 0.95
    max_regression_ratio: float = 0.10


class EvolutionGate:
    """Единственная точка допуска новой политики в прод."""

    def __init__(self, thresholds: EvolutionThresholds | None = None):
        self.thresholds = thresholds or EvolutionThresholds()

    def approve(self, old: PolicyMetrics, new: PolicyMetrics) -> bool:
        reward_gain = float(new.reward) - float(old.reward)
        old_reward = float(old.reward)
        regression_ratio = 0.0
        if old_reward > 0.0 and float(new.reward) < old_reward:
            regression_ratio = (old_reward - float(new.reward)) / old_reward

        if reward_gain < self.thresholds.min_reward_gain:
            raise EvolutionRejected("Reward gain too small")

        if regression_ratio > self.thresholds.max_regression_ratio:
            raise EvolutionRejected("Reward regression too large")

        if float(new.risk) > self.thresholds.max_risk:
            raise EvolutionRejected("Risk too high")

        if float(new.stability) < self.thresholds.min_stability:
            raise EvolutionRejected("Stability too low")

        return True
