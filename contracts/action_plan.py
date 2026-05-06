from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ActionPlan:
    plan_id: str = ''
    objective: str = ''
    steps: object = ()
