from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BusinessGoal:
    goal_name: str = ''
    priority: str = ''
    target_value: float = 0.0
