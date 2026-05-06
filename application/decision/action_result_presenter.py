from __future__ import annotations

"""Canonical presenter for raw action execution payloads.

Historical runtime imports are preserved via ``runtime.application.action_result_presenter``.
The canonical owner lives in ``core.application`` so result-shaping semantics stay
with the neutral application layer rather than a shadow decision namespace.
"""

from application.decision.action_result import ActionExecutionResult

CANON_CORE_DECISION_ACTION_RESULT_PRESENTER = True


def present_action_execution_result(raw: dict) -> ActionExecutionResult:
    return ActionExecutionResult(
        status=str(raw["status"]),
        action_type=str(raw["action_type"]),
        reason=raw.get("reason"),
        details=dict(raw),
    )


__all__ = [
    "CANON_CORE_DECISION_ACTION_RESULT_PRESENTER",
    "present_action_execution_result",
]
