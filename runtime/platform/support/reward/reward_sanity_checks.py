from __future__ import annotations


def reward_is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))

__all__ = [
    "reward_is_finite",
]
