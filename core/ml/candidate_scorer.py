from __future__ import annotations

from application.decisioning.candidate_scores import CandidateScoreSet
from kernel.decisioning.candidate_types import CandidateScore
from core.ml.contracts import MlCandidateScorer, MlScoringContext


class MlCandidateScorerImpl(MlCandidateScorer):
    def score(self, context: MlScoringContext) -> CandidateScoreSet:
        items: list[CandidateScore] = []

        for candidate in context.candidates.items:
            payload = candidate.payload
            model_score = float(payload.get("model_score", 0.0))
            items.append(
                CandidateScore(
                    candidate_id=candidate.candidate_id,
                    score_name="ml_model_score",
                    score_value=model_score,
                    explanation=(
                        "ML layer provides model score only. "
                        "It must not preselect winner or narrow action space."
                    ),
                )
            )

        return CandidateScoreSet.from_iterable(items)
