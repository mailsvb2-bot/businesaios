from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


CANON_GOAL_STRATEGY_SUPPORT = True


def _text(value: object) -> str:
    return str(value or '').strip().lower()


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


@dataclass(frozen=True)
class GoalStrategySupport:
    goal_family: str
    horizon: str
    support_level: str
    hints: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            'goal_family': self.goal_family,
            'horizon': self.horizon,
            'support_level': self.support_level,
            'hints': list(self.hints),
        }


class GoalStrategySupportBuilder:
    def build(self, *, goal: str, goal_family: str, metadata: Mapping[str, Any] | None = None) -> GoalStrategySupport:
        data = _safe_dict(metadata)
        token = _text(goal)
        hints: list[str] = []
        horizon = 'mid_horizon'
        if goal_family in {'revenue_growth', 'pipeline_growth'}:
            hints.append('prefer_verified_growth_actions')
        if goal_family == 'retention':
            hints.append('protect_existing_customers')
        if 'urgent' in token or 'today' in token or data.get('deadline'):
            horizon = 'near_horizon'
            hints.append('deadline_sensitive')
        if data.get('requires_approval'):
            hints.append('approval_gated')
        support_level = 'strong' if len(hints) >= 2 else ('moderate' if hints else 'baseline')
        return GoalStrategySupport(goal_family=goal_family, horizon=horizon, support_level=support_level, hints=tuple(hints))


__all__ = ['CANON_GOAL_STRATEGY_SUPPORT', 'GoalStrategySupport', 'GoalStrategySupportBuilder']
