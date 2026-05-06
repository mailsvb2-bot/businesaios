from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from shared.numbers import coerce_float


@dataclass(frozen=True)
class ScoreOutput:
    score: float
    confidence: float
    reasons: List[str] = field(default_factory=list)

    def bounded_score(self) -> float:
        return coerce_float(self.score, 0.0, minimum=0.0, maximum=1.0)

    def bounded_confidence(self) -> float:
        return coerce_float(self.confidence, 0.0, minimum=0.0, maximum=1.0)
