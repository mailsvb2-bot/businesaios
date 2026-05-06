from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SimulationGatePolicy:
    required_for_prefixes: tuple[str, ...] = ()
    min_score: float = 0.7
