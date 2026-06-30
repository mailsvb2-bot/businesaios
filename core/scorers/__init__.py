"""Canonical scoring surfaces for decision-time ranking.

Scorers may produce advisory scores and explanations. They must not execute
runtime effects and must not become a second decision center.
"""

from __future__ import annotations

from .bandit import ArmScore, Choice, choose_bandit_arm, score_bandit_arms
from .decision import DecisionCandidateScore, DecisionCandidateScorer, score_candidate

CANON_SCORERS_PUBLIC_API = True
__all__ = [
    "ArmScore",
    "CANON_SCORERS_PUBLIC_API",
    "Choice",
    "DecisionCandidateScore",
    "DecisionCandidateScorer",
    "choose_bandit_arm",
    "score_bandit_arms",
    "score_candidate",
]

