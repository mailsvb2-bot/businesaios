from __future__ import annotations

from runtime.platform.support.contracts.transition import Transition
from runtime.platform.support.reward.reward_model import RewardModel


class RewardService:
    def __init__(self, model: RewardModel) -> None:
        self._model = model

    def compute(self, transition: Transition) -> float:
        return self._model.score(transition)

__all__ = [
    "RewardService",
]
