from __future__ import annotations

from application.decisioning.candidate_scores import CandidateScoreSet
from core.growth.contracts import GrowthCandidateScorer, GrowthScoringContext


class GrowthService:
    def __init__(self, scorer: GrowthCandidateScorer) -> None:
        self._scorer = scorer

    def score_candidates(self, context: GrowthScoringContext) -> CandidateScoreSet:
        return self._scorer.score(context)
