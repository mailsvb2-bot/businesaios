from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CANON_HEADLESS_RUN_SELECTOR = True


@dataclass(frozen=True)
class RankedRun:
    run_id: str
    goal_score: float
    completed: bool
    stop_reason: str
    rank: int


@dataclass(frozen=True)
class RunSelector:
    """
    Ranks persisted runs by usefulness.

    Analysis only. Never affects execution.
    """

    def rank_runs(self, *, records: list[dict[str, Any]]) -> list[RankedRun]:
        enriched = []
        for record in records:
            feedback = dict(record.get("final_feedback") or {})
            score = self._safe_float(feedback.get("goal_score"))
            enriched.append(
                {
                    "run_id": str(record.get("run_id") or ""),
                    "goal_score": score,
                    "completed": bool(record.get("completed")),
                    "stop_reason": str(record.get("stop_reason") or ""),
                }
            )

        enriched.sort(
            key=lambda row: (
                1 if row["completed"] else 0,
                row["goal_score"],
            ),
            reverse=True,
        )

        return [
            RankedRun(
                run_id=row["run_id"],
                goal_score=row["goal_score"],
                completed=row["completed"],
                stop_reason=row["stop_reason"],
                rank=index + 1,
            )
            for index, row in enumerate(enriched)
        ]

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0


__all__ = [
    "CANON_HEADLESS_RUN_SELECTOR",
    "RankedRun",
    "RunSelector",
]
