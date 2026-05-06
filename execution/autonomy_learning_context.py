from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


CANON_AUTONOMY_LEARNING_CONTEXT = True


@dataclass(frozen=True)
class AutonomyLearningContext:
    tenant_id: str = ''
    business_id: str = ''
    goal_family: str = 'default'
    budget_posture: str = 'neutral'
    capability_health: dict[str, Any] = field(default_factory=dict)
    strategy_hints: tuple[dict[str, Any], ...] = ()
    retry_profile: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'tenant_id': str(self.tenant_id),
            'business_id': str(self.business_id),
            'goal_family': str(self.goal_family),
            'budget_posture': str(self.budget_posture),
            'capability_health': dict(self.capability_health),
            'strategy_hints': [dict(x) for x in self.strategy_hints],
            'retry_profile': dict(self.retry_profile),
        }


__all__ = ['CANON_AUTONOMY_LEARNING_CONTEXT', 'AutonomyLearningContext']
