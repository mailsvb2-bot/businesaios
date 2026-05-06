from __future__ import annotations

from contracts.action_result import ActionResult
from contracts.executable_action import ExecutableAction


CANON_INTERNAL_RUNNER_BASE = True


class AcceptedInternalRunner:
    """Canonical internal runner base.

    Keeps internal action semantics aligned on one path so status/payload fields
    do not drift across near-identical runners.
    """

    action_type: str = ""
    message: str = "accepted"

    def run(self, action: ExecutableAction) -> ActionResult:
        return ActionResult(
            action_id=action.action_id,
            status="accepted",
            message=str(self.message),
            payload={
                "action_type": str(self.action_type),
                "payload": dict(action.payload),
                "attempted": True,
                "executed": True,
                "verified": False,
                "operator_required": False,
            },
        )


__all__ = ["CANON_INTERNAL_RUNNER_BASE", "AcceptedInternalRunner"]
