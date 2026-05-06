from __future__ import annotations
from dataclasses import dataclass
from typing import Any

CANON_HEADLESS_CROSS_RUN_COMPARATOR = True

@dataclass(frozen=True)
class CrossRunComparison:
    baseline_run_id: str
    candidate_run_id: str
    baseline_goal_score: float
    candidate_goal_score: float
    delta_goal_score: float
    baseline_completed: bool
    candidate_completed: bool
    improved: bool
    summary: str

@dataclass(frozen=True)
class CrossRunComparator:
    """Compare two persisted headless runs without affecting execution."""

    def compare(self, *, baseline: dict[str, Any], candidate: dict[str, Any]) -> CrossRunComparison:
        baseline_score = self._score_from_feedback(dict(baseline.get("final_feedback") or {}))
        candidate_score = self._score_from_feedback(dict(candidate.get("final_feedback") or {}))
        baseline_completed = bool(baseline.get("completed"))
        candidate_completed = bool(candidate.get("completed"))
        delta = float(candidate_score) - float(baseline_score)
        return CrossRunComparison(
            baseline_run_id=str(baseline.get("run_id") or ""),
            candidate_run_id=str(candidate.get("run_id") or ""),
            baseline_goal_score=float(baseline_score),
            candidate_goal_score=float(candidate_score),
            delta_goal_score=float(delta),
            baseline_completed=baseline_completed,
            candidate_completed=candidate_completed,
            improved=delta > 0.0 or (candidate_completed and not baseline_completed),
            summary=f"candidate {candidate.get('run_id')} vs baseline {baseline.get('run_id')}: goal_score {candidate_score:.3f} vs {baseline_score:.3f}",
        )

    @staticmethod
    def _score_from_feedback(feedback: dict[str, Any]) -> float:
        try:
            return float(feedback.get("goal_score") or 0.0)
        except (TypeError, ValueError):
            return 0.0

__all__ = ["CANON_HEADLESS_CROSS_RUN_COMPARATOR", "CrossRunComparator", "CrossRunComparison"]
