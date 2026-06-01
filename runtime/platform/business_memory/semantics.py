from __future__ import annotations

from typing import Any

CANON_BUSINESS_MEMORY_SEMANTICS = True


TERMINAL_FAILURE_STATUSES = frozenset({'failed', 'execution_failed', 'verification_failed', 'unverified'})
OPERATOR_STATUSES = frozenset({'operator_required', 'approval_required', 'blocked_by_policy'})
SUCCESS_STATUSES = frozenset({'verified', 'goal_reached'})
EXECUTED_STATUSES = frozenset({'executed', 'verified', 'goal_reached'})
ATTEMPTED_STATUSES = frozenset({'attempted', 'executed', 'verified', 'goal_reached'})


def infer_memory_status(feedback: dict[str, Any] | None) -> str:
    payload = dict(feedback or {})
    status = str(
        payload.get('verification_status')
        or payload.get('evidence_status')
        or payload.get('status')
        or ''
    ).strip()
    if bool(payload.get('operator_required')):
        return 'operator_required'
    if bool(payload.get('verified')):
        return 'verified'
    if bool(payload.get('executed')):
        return 'executed'
    if bool(payload.get('attempted')):
        return 'attempted'
    return status or 'unknown'


def counts_as_success(status: str) -> bool:
    return str(status or '').strip() in SUCCESS_STATUSES


def counts_as_failure(status: str) -> bool:
    return str(status or '').strip() in TERMINAL_FAILURE_STATUSES


def counts_as_operator_handoff(status: str) -> bool:
    return str(status or '').strip() in OPERATOR_STATUSES


__all__ = [
    'CANON_BUSINESS_MEMORY_SEMANTICS',
    'EXECUTED_STATUSES',
    'ATTEMPTED_STATUSES',
    'SUCCESS_STATUSES',
    'TERMINAL_FAILURE_STATUSES',
    'OPERATOR_STATUSES',
    'counts_as_failure',
    'counts_as_operator_handoff',
    'counts_as_success',
    'infer_memory_status',
]
