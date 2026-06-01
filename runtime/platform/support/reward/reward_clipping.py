from __future__ import annotations


class RewardClipper:
    def __init__(self, low: float = -1.0, high: float = 1.0) -> None:
        self._low = low
        self._high = high

    def clip(self, reward: float) -> float:
        return max(self._low, min(self._high, reward))

__all__ = [
    "RewardClipper",
]
