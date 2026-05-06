from __future__ import annotations

from application.decisioning.candidate_scores import CandidateScoreSet
from core.ml.contracts import MlCandidateScorer, MlScoringContext


class MlService:
    def __init__(self, scorer: MlCandidateScorer) -> None:
        self._scorer = scorer

    def score_candidates(self, context: MlScoringContext) -> CandidateScoreSet:
        return self._scorer.score(context)
