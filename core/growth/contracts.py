from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from application.decisioning.candidate_collection import CandidateCollection
from application.decisioning.candidate_scores import CandidateScoreSet


@dataclass(frozen=True)
class GrowthScoringContext:
    tenant_id: str
    correlation_id: str
    candidates: CandidateCollection


class GrowthCandidateScorer(Protocol):
    def score(self, context: GrowthScoringContext) -> CandidateScoreSet:
        ...
