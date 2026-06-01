from __future__ import annotations

from application.decisioning.candidate_scores import CandidateScoreSet
from core.growth.contracts import GrowthCandidateScorer, GrowthScoringContext
from kernel.decisioning.candidate_types import CandidateScore


class SimpleGrowthCandidateScorer(GrowthCandidateScorer):
    def score(self, context: GrowthScoringContext) -> CandidateScoreSet:
        scored: list[CandidateScore] = []

        for item in context.candidates.items:
            payload = item.payload
            score_value = float(payload.get("priority_score", 0.0))
            scored.append(
                CandidateScore(
                    candidate_id=item.candidate_id,
                    score_name="growth_priority_score",
                    score_value=score_value,
                    explanation="Growth layer provides score only and does not select a winner.",
                )
            )

        return CandidateScoreSet.from_iterable(scored)
