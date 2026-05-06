from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from kernel.decisioning.candidate_types import CandidateEnvelope


@dataclass(frozen=True)
class CandidateCollection:
    items: Tuple[CandidateEnvelope, ...]

    @classmethod
    def from_iterable(cls, values: Iterable[CandidateEnvelope]) -> "CandidateCollection":
        return cls(items=tuple(values))

    def is_empty(self) -> bool:
        return not self.items
