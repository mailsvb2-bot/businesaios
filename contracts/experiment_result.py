from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentResult:
    experiment_id: str = ''
    winner: str = ''
    confidence: float = 0.0
