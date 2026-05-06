from __future__ import annotations
CANON_ERROR_MAPPER_FINAL_OWNER = True


from application.decision.action_errors import (
    ActionExecutionRejectedError,
    DecisionApplicationError,
    InvalidActionError,
)


def map_exception_to_error_code(exc: Exception) -> str:
    if isinstance(exc, InvalidActionError):
        return "invalid_action"
    if isinstance(exc, ActionExecutionRejectedError):
        return "action_rejected"
    if isinstance(exc, DecisionApplicationError):
        return "decision_application_error"
    return "internal_error"
