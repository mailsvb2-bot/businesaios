from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from collections.abc import Iterable

from .action_context import SafetyActionContext
from .control_result import ControlDecision, ControlStatus
from .exceptions import SafetyControlViolation


class SafetyControl(Protocol):
    control_name: str

    def evaluate(self, ctx: SafetyActionContext) -> ControlDecision: ...


@dataclass
class SafetyControlService:
    controls: Iterable[SafetyControl] = field(default_factory=tuple)

    def evaluate(self, ctx: SafetyActionContext) -> list[ControlDecision]:
        return [control.evaluate(ctx) for control in self.controls]

    def enforce(self, ctx: SafetyActionContext) -> list[ControlDecision]:
        decisions = self.evaluate(ctx)
        for decision in decisions:
            if decision.status in {ControlStatus.BLOCK, ControlStatus.REVIEW}:
                raise SafetyControlViolation(
                    control=decision.control,
                    reason=decision.reason,
                    details=decision.details,
                )
        return decisions
