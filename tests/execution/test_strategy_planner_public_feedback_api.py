from __future__ import annotations

from execution.strategy.strategic_planner import StrategicPlanner


def test_strategic_planner_exposes_public_apply_feedback_api() -> None:
    planner = StrategicPlanner()
    updated = planner.apply_feedback(metadata={'x': 1}, feedback_view={'next_mode': 'replan'}, feedback={'verified': True})
    assert isinstance(updated, dict)
