from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

CANON_DECISION_CANDIDATE_SPACE = True


@dataclass(frozen=True)
class CandidateScore:
    candidate_id: str
    score: float
    evidence: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class CandidateSpace:
    scores: tuple[CandidateScore, ...] = ()

    def ranked(self) -> tuple[CandidateScore, ...]:
        return tuple(sorted(self.scores, key=lambda item: item.score, reverse=True))


def build_candidate_space(scores: tuple[CandidateScore, ...] | list[CandidateScore]) -> CandidateSpace:
    return CandidateSpace(scores=tuple(scores))


__all__ = [
    "CANON_DECISION_CANDIDATE_SPACE",
    "CandidateScore",
    "CandidateSpace",
    "build_candidate_space",
]
