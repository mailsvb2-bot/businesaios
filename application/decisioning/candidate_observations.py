from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from kernel.decisioning.candidate_types import CandidateObservation


@dataclass(frozen=True)
class CandidateObservationSet:
    items: Tuple[CandidateObservation, ...]

    @classmethod
    def from_iterable(cls, values: Iterable[CandidateObservation]) -> "CandidateObservationSet":
        return cls(items=tuple(values))
