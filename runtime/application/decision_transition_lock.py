"""Single-owner execution transition for runtime application adapters.

This module never issues or selects a decision. It only validates and forwards an
already-issued canonical DecisionEnvelope to one execution owner exposing
``execute(envelope)``. Historical function names remain transition ABI, but raw
action and combined decide-and-execute surfaces are rejected.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.strategic_horizon.engine import CANONICAL_DECISION_OPTIMIZE_METHOD

CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_SINGLE_OWNER = True
CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_FAIL_CLOSED = True
CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_NO_DECISION_LOGIC = True
CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_ALLOWED_CALL = "execute"
CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_ENVELOPE_ONLY = True


class DecisionTransitionLockError(RuntimeError):
    pass


@dataclass(frozen=True)
class LockedDecisionTransitionCallable:
    name: str
    call: Callable[[object], Any]


FORBIDDEN_DECISION_OWNER_METHODS = (
    "issue",
    "decide",
    CANONICAL_DECISION_OPTIMIZE_METHOD,
    "decide_and_execute",
)


def _validate_envelope(envelope: object) -> None:
    decision = getattr(envelope, "decision", None)
    if decision is None:
        raise DecisionTransitionLockError(
            "canonical_decision_envelope_required"
        )
    if not str(getattr(decision, "decision_id", "") or "").strip():
        raise DecisionTransitionLockError(
            "decision_envelope_decision_id_required"
        )
    if not str(getattr(decision, "correlation_id", "") or "").strip():
        raise DecisionTransitionLockError(
            "decision_envelope_correlation_id_required"
        )
    if not str(getattr(decision, "action", "") or "").strip():
        raise DecisionTransitionLockError(
            "decision_envelope_action_required"
        )


def resolve_transition_execute_callable(
    owner: object,
) -> LockedDecisionTransitionCallable:
    validate_no_raw_decision_helpers(owner)
    execute = getattr(
        owner,
        CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_ALLOWED_CALL,
        None,
    )
    if not callable(execute):
        raise DecisionTransitionLockError(
            "decision_execution_owner_missing_execute"
        )
    return LockedDecisionTransitionCallable(
        name=CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_ALLOWED_CALL,
        call=execute,
    )


def validate_no_raw_decision_helpers(adapter: object) -> None:
    for name in FORBIDDEN_DECISION_OWNER_METHODS:
        value = getattr(adapter, name, None)
        if callable(value):
            raise DecisionTransitionLockError(
                f"transition_adapter_must_not_expose_raw_{name}"
            )


def execute_locked_transition_action(
    *,
    owner: object,
    action: object,
) -> Any:
    """Compatibility name; ``action`` must be a canonical envelope."""

    _validate_envelope(action)
    locked = resolve_transition_execute_callable(owner)
    return locked.call(action)


def execute_locked_application_action(
    *,
    owner: object,
    action: object,
) -> Any:
    """Compatibility application name with envelope-only semantics."""

    return execute_locked_transition_action(owner=owner, action=action)


__all__ = [
    "CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_ALLOWED_CALL",
    "CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_ENVELOPE_ONLY",
    "CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_FAIL_CLOSED",
    "CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_NO_DECISION_LOGIC",
    "CANON_RUNTIME_APPLICATION_DECISION_TRANSITION_SINGLE_OWNER",
    "DecisionTransitionLockError",
    "FORBIDDEN_DECISION_OWNER_METHODS",
    "LockedDecisionTransitionCallable",
    "execute_locked_transition_action",
    "execute_locked_application_action",
    "resolve_transition_execute_callable",
    "validate_no_raw_decision_helpers",
]
