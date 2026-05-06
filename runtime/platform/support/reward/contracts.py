from __future__ import annotations

from typing import Protocol
from runtime.platform.support.contracts.transition import Transition


class RewardScorer(Protocol):
    def score(self, transition: Transition) -> float:
        ...

__all__ = [
    "RewardScorer",
]
