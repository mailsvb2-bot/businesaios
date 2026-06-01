from __future__ import annotations

"""Canonical decision selection surface.

Candidate scoring is canonicalized under :mod:`core.scorers.decision` and this
module provides the thin winner-selection shell.
"""

from config.system_config import OptimizationObjective
from core.scorers.decision import DecisionCandidateScorer
from kernel.decision_candidate import DecisionCandidate


class DecisionSelector:
    def __init__(self, objective: OptimizationObjective | None = None) -> None:
        self._scorer = DecisionCandidateScorer(objective)

    def choose_candidate(self, candidates: list[DecisionCandidate]) -> DecisionCandidate | None:
        if not candidates:
            return None
        scored = (self._scorer.score(candidate) for candidate in candidates)
        winner = max(scored, key=lambda item: item.score)
        return winner.candidate

    select = choose_candidate
