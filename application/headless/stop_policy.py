from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CANON_HEADLESS_STOP_POLICY = True


@dataclass(frozen=True)
class StopDecision:
    should_stop: bool
    reason: str


@dataclass(frozen=True)
class HeadlessStopPolicy:
    """
    Conservative fail-closed stop policy.

    No strategy logic here.
    This object only determines whether the run should stop.

    Canonical execution semantics are:
    - attempted: the system tried to perform an action
    - executed: the system actually performed the action
    - verified: an external/evidence gate confirmed the effect
    """

    max_failures: int = 1

    def evaluate(
        self,
        *,
        step_index: int,
        max_steps: int,
        feedback: dict[str, Any],
        consecutive_failures: int,
        step_attempted: bool = False,
        step_executed: bool = False,
        step_verified: bool = False,
        operator_required: bool = False,
        step_ok: bool | None = None,
    ) -> StopDecision:
        # Backward compatibility for older call sites that still pass step_ok only.
        if step_ok is not None and not step_executed:
            step_executed = bool(step_ok)
        if bool(feedback.get("goal_reached")):
            return StopDecision(True, "goal_reached")
        if bool(operator_required) or bool(feedback.get("operator_required")):
            return StopDecision(True, "operator_required")
        if bool(step_attempted) and bool(step_executed) and not bool(step_verified):
            if int(consecutive_failures) >= int(self.max_failures):
                return StopDecision(True, "verification_failed")
        if not bool(step_executed) and int(consecutive_failures) >= int(self.max_failures):
            return StopDecision(True, "execution_failed")
        if int(step_index) + 1 >= int(max_steps):
            return StopDecision(True, "max_steps_reached")
        return StopDecision(False, "continue")


__all__ = [
    "CANON_HEADLESS_STOP_POLICY",
    "HeadlessStopPolicy",
    "StopDecision",
]
