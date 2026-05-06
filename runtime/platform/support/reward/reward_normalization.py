from __future__ import annotations

class RewardNormalizer:
    def __init__(self, scale: float = 1.0) -> None:
        self._scale = scale

    def normalize(self, reward: float) -> float:
        if self._scale == 0:
            return reward
        return reward / self._scale

__all__ = [
    "RewardNormalizer",
]
