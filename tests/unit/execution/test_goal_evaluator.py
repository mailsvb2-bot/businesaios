from __future__ import annotations

from dataclasses import dataclass

from execution.goal_evaluator import GoalEvaluator


@dataclass(frozen=True)
class StubRequest:
    max_steps: int = 3


def test_goal_evaluator_marks_goal_achieved_when_explicit_and_verified() -> None:
    evaluator = GoalEvaluator()
    result = evaluator.evaluate(request=StubRequest(max_steps=5), step_feedback={"goal_reached": True, "verified": True, "observed_progress_score": 1.0, "verification_confidence": 0.9}, step_verified=True, operator_required=False, consecutive_failures=0, step_index=1)
    assert result.achieved is True
    assert result.terminal is True
    assert result.continue_running is False
    assert result.reason == "goal_achieved"
    assert result.success_confidence >= 0.85
