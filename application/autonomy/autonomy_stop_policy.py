from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CANON_AUTONOMY_STOP_POLICY = True


@dataclass(frozen=True)
class StopEvaluation:
    completed: bool
    stop_reason: str | None = None
    consecutive_failures: int = 0
    should_stop: bool = False


class AutonomyStopPolicy:
    def __init__(self, *, contract: Any) -> None:
        self._contract = contract

    def evaluate(
        self,
        *,
        request: Any,
        step: Any,
        step_index: int,
        consecutive_failures: int,
    ) -> StopEvaluation:
        semantic_success = (
            bool(step.feedback.get("goal_evaluation", {}).get("achieved"))
            or bool(step.feedback.get("goal_reached"))
            or bool(step.verified)
        )
        next_consecutive_failures = 0 if semantic_success else consecutive_failures + 1
        goal_evaluation = self._contract._goal_evaluator.evaluate(
            request=request,
            step_feedback=step.feedback,
            step_verified=bool(step.verified),
            operator_required=bool(step.operator_required),
            consecutive_failures=next_consecutive_failures,
            step_index=step_index,
        )
        if goal_evaluation.terminal:
            return StopEvaluation(
                completed=bool(goal_evaluation.achieved),
                stop_reason=goal_evaluation.reason,
                consecutive_failures=next_consecutive_failures,
                should_stop=True,
            )
        decision = self._contract._stop_policy.evaluate(
            step_index=step_index,
            max_steps=int(request.max_steps),
            step_attempted=step.attempted,
            step_executed=step.executed,
            step_verified=step.verified,
            operator_required=step.operator_required,
            feedback=step.feedback,
            consecutive_failures=next_consecutive_failures,
        )
        return StopEvaluation(
            completed=bool(step.feedback.get("goal_evaluation", {}).get("achieved")) or bool(step.feedback.get("goal_reached")),
            stop_reason=decision.reason if decision.should_stop else None,
            consecutive_failures=next_consecutive_failures,
            should_stop=bool(decision.should_stop),
        )


__all__ = ["CANON_AUTONOMY_STOP_POLICY", "AutonomyStopPolicy", "StopEvaluation"]
