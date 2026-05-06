from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
import math

def require_non_empty(name: str, values: Sequence[object]) -> None:
    if not values:
        raise ValueError(f"{name} must be non-empty")

def require_same_length(name_a: str, a: Sequence[object], name_b: str, b: Sequence[object]) -> None:
    if len(a) != len(b):
        raise ValueError(f"{name_a} and {name_b} must have the same length")

def safe_dot(xs: Sequence[float], ys: Sequence[float]) -> float:
    require_same_length("xs", xs, "ys", ys)
    return float(sum(float(x) * float(y) for x, y in zip(xs, ys)))

def l2_norm(xs: Sequence[float]) -> float:
    return math.sqrt(sum(float(x) * float(x) for x in xs))

@dataclass(frozen=True)
class ScoredOption:
    name: str
    score: float
