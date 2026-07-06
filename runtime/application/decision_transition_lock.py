"""Single-owner transition lock for legacy runtime application ports.

This module does not issue decisions. It only validates that legacy
application-facing adapters delegate to one already-owned transition call
(`decide_and_execute`) instead of inventing local decision helpers.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.strategic_horizon.engine import CANONICAL_DECISION_OPTIMIZE_METHOD

CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_SINGLE_OWNER = True
CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_FAIL_CLOSED = True
CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_NO_DECISION_LOGIC = True
CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_ALLOWED_CALL = 'decide_and_execute'

class DecisionTransitionLockError(RuntimeError):
    pass


@dataclass(frozen=True)
class LockedDecisionTransitionCallable:
    name: str
    call: Callable[[object], dict[str, Any]]


FORBIDDEN_DECISION_OWNER_METHODS = (
    'issue',
    'decide',
    CANONICAL_DECISION_OPTIMIZE_METHOD,
)


def resolve_transition_execute_callable(owner: object) -> LockedDecisionTransitionCallable:
    execute = getattr(owner, CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_ALLOWED_CALL, None)
    if not callable(execute):
        raise DecisionTransitionLockError('decision_core_missing_decide_and_execute')
    return LockedDecisionTransitionCallable(
        name=CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_ALLOWED_CALL,
        call=execute,
    )


def validate_no_raw_decision_helpers(adapter: object) -> None:
    for name in FORBIDDEN_DECISION_OWNER_METHODS:
        value = getattr(adapter, name, None)
        if callable(value):
            raise DecisionTransitionLockError(f'transition_adapter_must_not_expose_raw_{name}')


def execute_locked_transition_action(*, owner: object, action: object) -> dict[str, Any]:
    locked = resolve_transition_execute_callable(owner)
    return locked.call(action)


def execute_locked_application_action(*, owner: object, action: object) -> dict[str, Any]:
    """Canonical application-facing name for the locked transition executor."""
    return execute_locked_transition_action(owner=owner, action=action)


__all__ = [
    'CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_ALLOWED_CALL',
    'CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_FAIL_CLOSED',
    'CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_NO_DECISION_LOGIC',
    'CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_SINGLE_OWNER',
    'DecisionTransitionLockError',
    'FORBIDDEN_DECISION_OWNER_METHODS',
    'LockedDecisionTransitionCallable',
    'execute_locked_transition_action',
    'execute_locked_application_action',
    'resolve_transition_execute_callable',
    'validate_no_raw_decision_helpers',
]
