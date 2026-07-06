from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from ..action_context import SafetyActionContext
from .models import RollbackPlan

RollbackBuilder = Callable[[SafetyActionContext], RollbackPlan]


class RollbackRegistry(Protocol):
    def register(self, action: str, builder: RollbackBuilder) -> None: ...

    def plan_for(self, ctx: SafetyActionContext) -> RollbackPlan: ...


@dataclass
class InMemoryRollbackRegistry:
    builders: dict[str, RollbackBuilder] = field(default_factory=dict)

    def register(self, action: str, builder: RollbackBuilder) -> None:
        self.builders[str(action)] = builder

    def plan_for(self, ctx: SafetyActionContext) -> RollbackPlan:
        builder = self.builders.get(str(ctx.action))
        if builder is None:
            return RollbackPlan(source_action=str(ctx.action), steps=())
        return builder(ctx)


__all__ = ['InMemoryRollbackRegistry', 'RollbackBuilder', 'RollbackRegistry']
