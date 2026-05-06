from __future__ import annotations

CANON_CORE_DECISION_ACTION_ERRORS = True


class DecisionApplicationError(Exception):
    """Base application-level decision error."""


class InvalidActionError(DecisionApplicationError):
    """Action request is invalid."""


class ActionExecutionRejectedError(DecisionApplicationError):
    """Action was rejected by governance."""


__all__ = [
    "ActionExecutionRejectedError",
    "CANON_CORE_DECISION_ACTION_ERRORS",
    "DecisionApplicationError",
    "InvalidActionError",
]
