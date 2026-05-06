from __future__ import annotations

from runtime.platform.support.contracts.transition import Transition


class RewardModel:
    def score(self, transition: Transition) -> float:
        return float(transition.reward.value)

__all__ = [
    "RewardModel",
]
