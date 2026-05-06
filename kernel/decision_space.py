from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
from kernel.decision_candidate import DecisionCandidate


@dataclass
class DecisionSpace:
    candidates: List[DecisionCandidate] = field(default_factory=list)

    def viable(self) -> list[DecisionCandidate]:
        return [candidate for candidate in self.candidates if candidate.score > 0.0]
