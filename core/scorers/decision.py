from __future__ import annotations

from dataclasses import dataclass

from config.system_config import OptimizationObjective
from kernel.decision_candidate import DecisionCandidate


@dataclass(frozen=True)
class DecisionCandidateScore:
    candidate: DecisionCandidate
    score: float


class DecisionCandidateScorer:
    def __init__(self, objective: OptimizationObjective | None = None) -> None:
        self._objective = objective or OptimizationObjective()

    def score(self, candidate: DecisionCandidate) -> DecisionCandidateScore:
        value = candidate.objective_score(
            risk_penalty_weight=self._objective.risk_penalty_weight,
            confidence_penalty_weight=self._objective.confidence_penalty_weight,
        )
        return DecisionCandidateScore(candidate=candidate, score=float(value))



def score_candidate(
    candidate: DecisionCandidate,
    *,
    objective: OptimizationObjective | None = None,
) -> DecisionCandidateScore:
    return DecisionCandidateScorer(objective).score(candidate)
