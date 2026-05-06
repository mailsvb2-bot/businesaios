from __future__ import annotations

from application.decisioning.candidate_scores import CandidateScoreSet
from kernel.decisioning.candidate_types import CandidateScore
from config.economics_domain_policy import DEFAULT_ECONOMICS_SIGNAL_DEFAULTS
from core.economics.contracts import EconomicsCandidateScorer, EconomicsScoringContext


class EconomicsCandidateScorerImpl(EconomicsCandidateScorer):
    def score(self, context: EconomicsScoringContext) -> CandidateScoreSet:
        items: list[CandidateScore] = []

        for candidate in context.candidates.items:
            payload = candidate.payload
            margin_value = float(payload.get("expected_margin", DEFAULT_ECONOMICS_SIGNAL_DEFAULTS.zero_amount))
            items.append(
                CandidateScore(
                    candidate_id=candidate.candidate_id,
                    score_name="expected_margin_score",
                    score_value=margin_value,
                    explanation=(
                        "Economics layer provides comparable economics score only. "
                        "It does not choose or resolve the final business action."
                    ),
                )
            )

        return CandidateScoreSet.from_iterable(items)
