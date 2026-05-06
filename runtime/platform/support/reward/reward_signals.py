from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RewardSignal:
    name: str
    value: float

__all__ = [
    "RewardSignal",
]
