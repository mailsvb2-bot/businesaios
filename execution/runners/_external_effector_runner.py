from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from contracts.action_result import ActionResult
from contracts.executable_action import ExecutableAction
from execution.effectors.router import EffectorRouter


@dataclass
class ExternalEffectorRunner:
    action_type: str
    router: EffectorRouter = field(default_factory=EffectorRouter)

    def run(self, action: ExecutableAction | dict[str, Any]) -> ActionResult:
        if isinstance(action, ExecutableAction):
            action_dict = action.as_dict()
            action_id = action.action_id
        else:
            action_dict = dict(action)
            action_id = str(action_dict.get("action_id") or "")
        result = self.router.execute(action_type=self.action_type, action=action_dict)
        action_result = result.to_action_result(action_id=action_id, action_type=self.action_type)
        payload = dict(action_result.payload or {})
        effector = dict(payload.get("effector") or {}) if isinstance(payload.get("effector"), dict) else {}
        payload.setdefault("attempted", bool(effector.get("attempted", False)))
        payload.setdefault("executed", bool(effector.get("executed", False)))
        payload.setdefault("verified", bool(effector.get("verified", False)))
        payload.setdefault("operator_required", bool(effector.get("operator_required", False)))
        return ActionResult(
            action_id=action_result.action_id,
            status=action_result.status,
            message=action_result.message,
            payload=payload,
        )


__all__ = ["ExternalEffectorRunner"]
