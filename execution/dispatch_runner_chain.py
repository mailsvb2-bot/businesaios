from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from contracts.action_result import ActionResult
from contracts.executable_action import ExecutableAction
from execution.action_idempotency import ActionIdempotency
from execution.action_validator import ActionValidator


class ActionRunPort(Protocol):
    def run(self, action: ExecutableAction) -> ActionResult: ...


@dataclass
class DispatchRunnerChain:
    validator: ActionValidator
    runner: ActionRunPort
    idempotency: ActionIdempotency

    def dispatch(self, action: ExecutableAction) -> ActionResult:
        ok, errors = self.validator.validate(action)
        if not ok:
            return ActionResult(
                action_id=action.action_id,
                status='rejected',
                message='validation_failed',
                payload={'errors': errors},
            )
        if not self.idempotency.allow(action.action_id):
            return ActionResult(
                action_id=action.action_id,
                status='duplicate',
                message='duplicate_action',
            )
        return self.runner.run(action)


__all__ = ["ActionRunPort", "DispatchRunnerChain"]
