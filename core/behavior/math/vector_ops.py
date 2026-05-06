from __future__ import annotations

def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / float(len(values))


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0.0:
        return 0.0
    return numerator / denominator
