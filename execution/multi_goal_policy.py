from __future__ import annotations

from typing import Any, Mapping

from execution.goal_strategy_support import GoalStrategySupportBuilder


CANON_MULTI_GOAL_POLICY = True


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


class MultiGoalPolicy:
    def __init__(self) -> None:
        self._support_builder = GoalStrategySupportBuilder()

    def score(self, *, item: Any, goal_family: str) -> float:
        if not getattr(item, 'active', False) or getattr(item, 'status', '') == 'completed':
            return -1.0
        if getattr(item, 'blocked', False):
            return 0.0
        progress_penalty = float(getattr(item, 'progress_score', 0.0)) * 10.0
        family_bias = 4.0 if goal_family in {'revenue_growth', 'pipeline_growth'} else 0.0
        return (float(getattr(item, 'priority', 0.0)) * 0.45) + (float(getattr(item, 'urgency', 0.0)) * 0.45) + (float(getattr(item, 'budget_weight', 1.0)) * 10.0) + family_bias - progress_penalty

    def next_status(self, *, feedback_view: Mapping[str, Any]) -> str:
        if feedback_view.get('achieved'):
            return 'completed'
        if feedback_view.get('blocked'):
            return 'blocked'
        return 'queued'

    def support(self, *, goal: str, goal_family: str, metadata: Mapping[str, Any] | None) -> dict[str, Any]:
        return self._support_builder.build(goal=goal, goal_family=goal_family, metadata=metadata).to_dict()


__all__ = ['CANON_MULTI_GOAL_POLICY', 'MultiGoalPolicy']
