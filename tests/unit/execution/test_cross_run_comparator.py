from __future__ import annotations

from execution.cross_run_comparator import CrossRunComparator


def test_cross_run_comparator_detects_improvement() -> None:
    comparator = CrossRunComparator()
    result = comparator.compare(
        baseline={
            "run_id": "run-1",
            "completed": False,
            "final_feedback": {"goal_score": 0.30},
        },
        candidate={
            "run_id": "run-2",
            "completed": True,
            "final_feedback": {"goal_score": 0.80},
        },
    )
    assert result.improved is True
    assert result.delta_goal_score == 0.5


def test_cross_run_comparator_detects_no_improvement() -> None:
    comparator = CrossRunComparator()
    result = comparator.compare(
        baseline={
            "run_id": "run-1",
            "completed": True,
            "final_feedback": {"goal_score": 0.90},
        },
        candidate={
            "run_id": "run-2",
            "completed": True,
            "final_feedback": {"goal_score": 0.70},
        },
    )
    assert result.improved is False
