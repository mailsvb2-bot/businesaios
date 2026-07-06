from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from application.effects.effect_outcome_vocabulary import normalize_outcome_status, outcome_is_verified

CANON_EXECUTION_FEEDBACK_CONTRACT = True


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _safe_list(value: object) -> list[str]:
    if isinstance(value, list | tuple | set):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or '').strip()
    return [text] if text else []


def _text(value: object) -> str:
    return str(value or '').strip()


def canonical_execution_feedback(
    *,
    feedback: Mapping[str, Any] | None = None,
    verification_result: Mapping[str, Any] | None = None,
    action: Mapping[str, Any] | None = None,
    execution_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    feedback_payload = _safe_dict(feedback)
    verification_payload = _safe_dict(verification_result)
    action_payload = _safe_dict(action)
    receipt_payload = _safe_dict(execution_receipt)
    verification = _safe_dict(verification_payload.get('verification'))
    outcome = _safe_dict(verification.get('outcome'))
    evidence_bundle = _safe_dict(verification_payload.get('evidence_bundle'))
    router_result = _safe_dict(_safe_dict(feedback_payload.get('evidence')).get('router_result'))

    action_type = _text(
        action_payload.get('action_type')
        or receipt_payload.get('action_type')
        or outcome.get('action_type')
        or router_result.get('action_type')
        or evidence_bundle.get('action_type')
        or feedback_payload.get('action')
    )
    action_id = _text(
        action_payload.get('action_id')
        or receipt_payload.get('action_id')
        or outcome.get('action_id')
        or router_result.get('external_id')
        or evidence_bundle.get('action_id')
        or feedback_payload.get('action_id')
    )
    decision_id = _text(action_payload.get('decision_id') or receipt_payload.get('decision_id') or feedback_payload.get('decision_id'))
    correlation_id = _text(action_payload.get('correlation_id') or receipt_payload.get('correlation_id') or feedback_payload.get('correlation_id'))

    attempted = bool(feedback_payload.get('attempted', receipt_payload.get('attempted', False)))
    executed = bool(feedback_payload.get('executed', receipt_payload.get('executed', receipt_payload.get('ok', False))))
    operator_required = bool(feedback_payload.get('operator_required', receipt_payload.get('operator_required', False)))
    retryable = bool(
        feedback_payload.get('retryable', verification.get('retryable', router_result.get('retryable', False)))
    )

    status = normalize_outcome_status(
        feedback_payload.get('verification_status')
        or feedback_payload.get('evidence_status')
        or verification.get('status')
        or router_result.get('status')
        or outcome.get('verification_status'),
        verified=feedback_payload.get('verified', verification_payload.get('verified', verification.get('verified', None))),
        retryable=retryable,
        default='unknown',
    )
    verified = outcome_is_verified(
        status,
        verified=feedback_payload.get('verified', verification_payload.get('verified', verification.get('verified', False))),
        retryable=retryable,
    )
    confidence = feedback_payload.get('verification_confidence')
    if confidence in {None, ''}:
        confidence = verification.get('confidence')
    if confidence in {None, ''}:
        confidence = router_result.get('confidence')
    if confidence in {None, ''}:
        confidence = 1.0 if verified else 0.0

    external_refs = (
        _safe_list(feedback_payload.get('external_refs'))
        or _safe_list(verification.get('external_refs'))
        or _safe_list(router_result.get('external_refs'))
        or _safe_list(evidence_bundle.get('external_refs'))
    )
    message = _text(
        feedback_payload.get('error')
        or verification.get('message')
        or router_result.get('message')
        or outcome.get('reason')
        or receipt_payload.get('summary')
    )
    source_of_truth = _text(verification.get('source_of_truth') or router_result.get('source') or 'feedback_contract')

    return {
        'action_type': action_type,
        'action_id': action_id,
        'decision_id': decision_id,
        'correlation_id': correlation_id,
        'attempted': attempted,
        'executed': executed,
        'verified': verified,
        'operator_required': operator_required,
        'verification_status': status,
        'evidence_status': status,
        'verification_confidence': float(confidence or 0.0),
        'retryable': retryable,
        'external_refs': external_refs,
        'external_ref': external_refs[0] if external_refs else None,
        'message': message,
        'source_of_truth': source_of_truth,
    }


def canonical_persisted_outcome(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _safe_dict(snapshot)
    status = normalize_outcome_status(
        payload.get('verification_status') or payload.get('evidence_status'),
        verified=payload.get('verified'),
        retryable=payload.get('retryable'),
        default='unknown',
    )
    return {
        'verified': outcome_is_verified(status, verified=payload.get('verified'), retryable=payload.get('retryable')),
        'status': status,
        'code': _text(payload.get('code') or status),
        'message': _text(payload.get('message')),
        'source_of_truth': _text(payload.get('source_of_truth')),
        'confidence': payload.get('verification_confidence'),
        'external_refs': list(_safe_list(payload.get('external_refs'))),
        'action_type': _text(payload.get('action_type')),
        'action_id': _text(payload.get('action_id')),
        'decision_id': _text(payload.get('decision_id')),
        'correlation_id': _text(payload.get('correlation_id')),
        'attempted': bool(payload.get('attempted', False)),
        'executed': bool(payload.get('executed', False)),
        'operator_required': bool(payload.get('operator_required', False)),
        'retryable': bool(payload.get('retryable', False)),
    }


def canonical_world_state_row(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _safe_dict(snapshot)
    status = normalize_outcome_status(
        payload.get('verification_status') or payload.get('status'),
        verified=payload.get('verified'),
        retryable=payload.get('retryable'),
        default='unknown',
    )
    return {
        'action_type': _text(payload.get('action_type')),
        'action_id': _text(payload.get('action_id')),
        'decision_id': _text(payload.get('decision_id')),
        'correlation_id': _text(payload.get('correlation_id')),
        'verified': outcome_is_verified(status, verified=payload.get('verified'), retryable=payload.get('retryable')),
        'verification_status': status,
        'message': _text(payload.get('message')),
        'external_refs': list(_safe_list(payload.get('external_refs'))),
        'source_of_truth': _text(payload.get('source_of_truth')),
        'attempted': bool(payload.get('attempted', False)),
        'executed': bool(payload.get('executed', False)),
        'operator_required': bool(payload.get('operator_required', False)),
        'retryable': bool(payload.get('retryable', False)),
    }


def canonical_headless_step_artifact(
    *,
    feedback: Mapping[str, Any] | None = None,
    action: Mapping[str, Any] | None = None,
    execution_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = canonical_execution_feedback(
        feedback=feedback,
        action=action,
        execution_receipt=execution_receipt,
    )
    return {
        'execution_feedback': dict(snapshot),
        'payload': dict(_safe_dict(action).get('payload') or {}),
    }


__all__ = [
    'CANON_EXECUTION_FEEDBACK_CONTRACT',
    'canonical_execution_feedback',
    'canonical_headless_step_artifact',
    'canonical_persisted_outcome',
    'canonical_world_state_row',
]
