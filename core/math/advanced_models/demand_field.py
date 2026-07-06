from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class DemandSource:
    x: float
    y: float
    weight: float

def demand_potential(*, x: float, y: float, sources: Sequence[DemandSource], epsilon: float = 1e-6) -> float:
    potential = 0.0
    for source in sources:
        dx = float(x) - source.x
        dy = float(y) - source.y
        distance = math.sqrt(dx * dx + dy * dy) + epsilon
        potential += source.weight / distance
    return potential
