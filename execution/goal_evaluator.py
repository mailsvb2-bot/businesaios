from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from config.decision_safety_policy import DEFAULT_GOAL_EVALUATION_POLICY


CANON_GOAL_EVALUATOR = True


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


@dataclass(frozen=True)
class GoalEvaluation:
    achieved: bool
    terminal: bool
    continue_running: bool
    success_confidence: float
    completion_ratio: float
    reason: str
    signals: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "achieved": bool(self.achieved),
            "terminal": bool(self.terminal),
            "continue_running": bool(self.continue_running),
            "success_confidence": float(self.success_confidence),
            "completion_ratio": float(self.completion_ratio),
            "reason": str(self.reason),
            "signals": list(self.signals),
        }


class GoalEvaluator:
    def evaluate(
        self,
        *,
        request: Any,
        step_feedback: Mapping[str, Any] | None,
        step_verified: bool,
        operator_required: bool,
        consecutive_failures: int,
        step_index: int,
    ) -> GoalEvaluation:
        feedback = _safe_dict(step_feedback)
        signals: list[str] = []

        explicit_goal_reached = bool(feedback.get("goal_reached"))
        verified = bool(step_verified or feedback.get("verified"))
        blocked = bool(feedback.get("blocked_by_policy"))
        approval_required = bool(feedback.get("approval_required") or operator_required)
        progress_score = max(0.0, min(1.0, _safe_float(feedback.get("observed_progress_score"))))
        goal_score = max(0.0, min(1.0, _safe_float(feedback.get("goal_score"))))
        verification_confidence = max(0.0, min(1.0, _safe_float(feedback.get("verification_confidence"))))

        completion_ratio = max(progress_score, goal_score)
        policy = DEFAULT_GOAL_EVALUATION_POLICY
        success_confidence = 0.0
        if explicit_goal_reached:
            success_confidence += policy.explicit_goal_reached_weight
            signals.append("explicit_goal_reached")
        if verified:
            success_confidence += policy.verified_weight
            signals.append("verified")
        if verification_confidence > 0.0:
            success_confidence += policy.verification_confidence_weight * verification_confidence
            signals.append("verification_confidence")
        if completion_ratio > 0.0:
            signals.append("completion_ratio")
        success_confidence = max(0.0, min(1.0, float(success_confidence)))

        if blocked:
            return GoalEvaluation(False, True, False, success_confidence, completion_ratio, "policy_blocked", tuple(signals))
        if approval_required:
            return GoalEvaluation(False, True, False, success_confidence, completion_ratio, "operator_required", tuple(signals))
        if explicit_goal_reached and (verified or verification_confidence >= policy.verification_confidence_goal_achieved_threshold):
            return GoalEvaluation(True, True, False, max(success_confidence, policy.achieved_confidence_floor), max(completion_ratio, 1.0), "goal_achieved", tuple(signals))
        if int(consecutive_failures) >= policy.repeated_failure_terminal_threshold and completion_ratio <= 0.0:
            return GoalEvaluation(False, True, False, success_confidence, completion_ratio, "repeated_failures_without_progress", tuple(signals))
        return GoalEvaluation(False, False, True, success_confidence, completion_ratio, "continue", tuple(signals))


__all__ = ["CANON_GOAL_EVALUATOR", "GoalEvaluation", "GoalEvaluator"]
