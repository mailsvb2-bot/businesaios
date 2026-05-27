from __future__ import annotations

from typing import Iterable

from runtime.platform.support.reward.reward_signals import RewardSignal


class RewardAggregation:
    def aggregate(self, signals: Iterable[RewardSignal]) -> float:
        return sum(signal.value for signal in signals)

__all__ = [
    "RewardAggregation",
]
