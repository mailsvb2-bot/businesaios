from __future__ import annotations

"""Shared guard threshold primitives.

These helpers keep simple threshold checks in one place so guard namespaces can
remain thin adapters instead of growing their own duplicated comparison logic.
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ThresholdCheck:
    name: str
    threshold: float
    comparator: Callable[[float, float], bool]

    def evaluate(self, value: object, *, coerce: Callable[[object], float] | None = None) -> bool:
        normalizer = coerce or _coerce_float
        return bool(self.comparator(normalizer(value), float(self.threshold)))


def _coerce_float(value: object) -> float:
    if isinstance(value, bool):
        return float(int(value))
    return float(value)


def less_than(value: object, threshold: float) -> bool:
    return ThresholdCheck(name='lt', threshold=threshold, comparator=lambda current, limit: current < limit).evaluate(value)


def less_equal(value: object, threshold: float) -> bool:
    return ThresholdCheck(name='le', threshold=threshold, comparator=lambda current, limit: current <= limit).evaluate(value)


def greater_equal(value: object, threshold: float) -> bool:
    return ThresholdCheck(name='ge', threshold=threshold, comparator=lambda current, limit: current >= limit).evaluate(value)


def score_or_zero(*, score: object, blocked: object) -> float:
    blocked_flag = bool(blocked)
    if blocked_flag:
        return 0.0
    current = _coerce_float(score)
    return current if current >= 0.0 else 0.0
