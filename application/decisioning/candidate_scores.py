from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from kernel.decisioning.candidate_types import CandidateScore


@dataclass(frozen=True)
class CandidateScoreSet:
    items: Tuple[CandidateScore, ...]

    @classmethod
    def from_iterable(cls, values: Iterable[CandidateScore]) -> "CandidateScoreSet":
        return cls(items=tuple(values))
