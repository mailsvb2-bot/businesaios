from __future__ import annotations

from runtime.platform.support.contracts.transition import Transition
from runtime.platform.support.reward.reward_service import RewardService
from runtime.platform.support.reward.reward_normalization import RewardNormalizer
from runtime.platform.support.reward.reward_clipping import RewardClipper


class RewardPipeline:
    def __init__(
        self,
        service: RewardService,
        normalizer: RewardNormalizer,
        clipper: RewardClipper,
    ) -> None:
        self._service = service
        self._normalizer = normalizer
        self._clipper = clipper

    def compute(self, transition: Transition) -> float:
        value = self._service.compute(transition)
        value = self._normalizer.normalize(value)
        value = self._clipper.clip(value)
        return value

__all__ = [
    "RewardPipeline",
]
