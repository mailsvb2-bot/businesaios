from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple


@dataclass(frozen=True)
class CandidateScore:
    candidate: str
    score: float
    source: str

def build_candidate_space(
    *, candidates: Sequence[str], scores: Sequence[float], source: str
) -> tuple[CandidateScore, ...]:
    out = []
    for c, s in zip(candidates, scores, strict=False):
        out.append(CandidateScore(candidate=str(c), score=float(s), source=str(source)))
    return tuple(out)
