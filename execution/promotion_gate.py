from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CANON_HEADLESS_PROMOTION_GATE = True


@dataclass(frozen=True)
class PromotionDecision:
    approved: bool
    reason: str


@dataclass(frozen=True)
class PromotionGate:
    """
    Decides whether a run is safe enough to promote as a baseline.

    Governance only. Never affects execution.
    """

    min_goal_score: float = 0.80
    require_completed: bool = True

    def evaluate(self, *, record: dict[str, Any]) -> PromotionDecision:
        feedback = dict(record.get("final_feedback") or {})
        goal_score = self._safe_float(feedback.get("goal_score"))
        retry = feedback.get("retry_classification")
        retry_kind = ""
        if isinstance(retry, dict):
            retry_kind = str(retry.get("kind") or "")

        if self.require_completed and not bool(record.get("completed")):
            return PromotionDecision(False, "run_not_completed")

        if str(record.get("stop_reason") or "") != "goal_reached":
            return PromotionDecision(False, "stop_reason_not_goal_reached")

        if retry_kind == "operator_required":
            return PromotionDecision(False, "operator_required")

        if goal_score < float(self.min_goal_score):
            return PromotionDecision(False, "goal_score_below_threshold")

        return PromotionDecision(True, "approved")

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0


__all__ = [
    "CANON_HEADLESS_PROMOTION_GATE",
    "PromotionDecision",
    "PromotionGate",
]
