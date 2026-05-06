from __future__ import annotations

"""Thin compatibility alias for the canonical runtime application transition lock.

This module must remain module-thin and forward-only.
It exists solely for backward import compatibility.
"""

from runtime.application.decision_transition_lock import (
    CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_ALLOWED_CALL as CANON_RUNTIME_APPLICATION_DECISION_COMPAT_ALLOWED_CALL,
    CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_FAIL_CLOSED as CANON_RUNTIME_APPLICATION_DECISION_COMPAT_FAIL_CLOSED,
    CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_NO_DECISION_LOGIC as CANON_RUNTIME_APPLICATION_DECISION_COMPAT_NO_DECISION_LOGIC,
    CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_SINGLE_OWNER as CANON_RUNTIME_APPLICATION_DECISION_COMPAT_SINGLE_OWNER,
    DecisionTransitionLockError as DecisionCompatLockError,
    FORBIDDEN_DECISION_OWNER_METHODS,
    execute_locked_transition_action as execute_locked_application_action,
    resolve_transition_execute_callable as resolve_decide_and_execute_callable,
    validate_no_raw_decision_helpers,
)

CANON_RUNTIME_APPLICATION_DECISION_COMPAT_ALIAS_ONLY = True

__all__ = [
    'CANON_RUNTIME_APPLICATION_DECISION_COMPAT_ALLOWED_CALL',
    'CANON_RUNTIME_APPLICATION_DECISION_COMPAT_ALIAS_ONLY',
    'CANON_RUNTIME_APPLICATION_DECISION_COMPAT_FAIL_CLOSED',
    'CANON_RUNTIME_APPLICATION_DECISION_COMPAT_NO_DECISION_LOGIC',
    'CANON_RUNTIME_APPLICATION_DECISION_COMPAT_SINGLE_OWNER',
    'DecisionCompatLockError',
    'FORBIDDEN_DECISION_OWNER_METHODS',
    'execute_locked_application_action',
    'resolve_decide_and_execute_callable',
    'validate_no_raw_decision_helpers',
]
