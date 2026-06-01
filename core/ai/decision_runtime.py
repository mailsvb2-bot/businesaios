from __future__ import annotations

from application.decision_runtime.runtime import (
    apply_state_constraints as _apply_state_constraints,
)
from application.decision_runtime.runtime import (
    build_trace as _build_trace,
)
from application.decision_runtime.runtime import (
    extract_correlation_key as _extract_correlation_key,
)
from application.decision_runtime.runtime import (
    select_and_propose as _select_and_propose,
)
from application.decision_runtime.runtime import (
    validate_and_gate_action as _validate_and_gate_action,
)
from core.decision.ai_decision_trace import TraceBuilder

CANON_DECISION_RUNTIME_COMPAT = True


def extract_correlation_key(state):
    return _extract_correlation_key(state)


def build_trace(*, state, issuer_id: str, envelope_version: int):
    return _build_trace(state=state, issuer_id=issuer_id, envelope_version=envelope_version)


def apply_state_constraints(*, state, trace, user_id: str):
    return _apply_state_constraints(state=state, trace=trace, user_id=user_id)


def select_and_propose(*, selector, state, trace):
    return _select_and_propose(selector=selector, state=state, trace=trace)


def validate_and_gate_action(*, schemas, state, out, user_id: str, events, trace) -> int:
    return _validate_and_gate_action(
        schemas=schemas,
        state=state,
        out=out,
        user_id=user_id,
        events=events,
        trace=trace,
    )


__all__ = [
    'TraceBuilder',
    'extract_correlation_key',
    'build_trace',
    'apply_state_constraints',
    'select_and_propose',
    'validate_and_gate_action',
    'CANON_DECISION_RUNTIME_COMPAT',
]
