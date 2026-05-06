from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CANON_HEADLESS_GOAL_SCORE = True


@dataclass(frozen=True)
class GoalScore:
    value: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class GoalScoreEngine:
    """
    Thin progress scoring layer.

    Hard rule:
    - this is NOT a second decision core
    - this does NOT infer semantics from free-text goal text
    - this only scores explicit observed progress fields already present in feedback
    """

    def score(self, *, goal: str, feedback: dict[str, Any], step_ok: bool) -> GoalScore:
        del goal
        reasons: list[str] = []
        score = 0.0

        if step_ok:
            score += 0.15
            reasons.append("step_ok")

        goal_reached = feedback.get("goal_reached")
        if isinstance(goal_reached, bool) and goal_reached:
            score += 0.60
            reasons.append("goal_reached")

        explicit_progress = feedback.get("observed_progress_score")
        if isinstance(explicit_progress, (int, float)):
            bounded = max(0.0, min(1.0, float(explicit_progress)))
            if bounded > 0.0:
                score += 0.25 * bounded
                reasons.append("observed_progress_score")

        return GoalScore(
            value=max(0.0, min(1.0, float(score))),
            reasons=tuple(reasons),
        )


__all__ = [
    "CANON_HEADLESS_GOAL_SCORE",
    "GoalScore",
    "GoalScoreEngine",
]
