from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from application.effects.canonical_execution_feedback import canonical_execution_feedback
from application.effects.effect_outcome_vocabulary import normalize_outcome_status


CANON_RUN_ARTIFACT_CONTRACT = True


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _safe_list(value: object) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or '').strip()
    return [text] if text else []


def _text(value: object) -> str:
    return str(value or '').strip()


def canonical_goal_execution_step(step: Any) -> dict[str, Any]:
    execution_feedback = dict(
        _safe_dict(getattr(step, 'execution_feedback', None))
        or canonical_execution_feedback(feedback=_safe_dict(getattr(step, 'feedback', None)))
    )
    external_refs = (
        _safe_list(execution_feedback.get('external_refs'))
        or _safe_list(_safe_dict(getattr(step, 'feedback', None)).get('external_refs'))
    )
    external_ref = _text(getattr(step, 'external_ref', None) or (external_refs[0] if external_refs else '')) or None
    verification_status = normalize_outcome_status(
        getattr(step, 'verification_status', None) or execution_feedback.get('verification_status'),
        verified=getattr(step, 'verified', False),
        retryable=execution_feedback.get('retryable', False),
        default='unknown',
    )
    return {
        'step_index': int(getattr(step, 'step_index', 0) or 0),
        'decision_id': _text(getattr(step, 'decision_id', None)),
        'action_id': _text(getattr(step, 'action_id', None)),
        'action_type': _text(getattr(step, 'action', None) or execution_feedback.get('action_type')),
        'status': _text(getattr(step, 'status', None)),
        'attempted': bool(getattr(step, 'attempted', False)),
        'executed': bool(getattr(step, 'executed', False)),
        'verified': bool(getattr(step, 'verified', False)),
        'operator_required': bool(getattr(step, 'operator_required', False)),
        'correlation_id': _text(getattr(step, 'correlation_id', None)),
        'reason': _text(getattr(step, 'reason', None)),
        'verification_status': verification_status,
        'external_refs': external_refs,
        'external_ref': external_ref,
        'execution_feedback': execution_feedback,
        'payload': dict(_safe_dict(getattr(step, 'payload', None))),
        'evidence': dict(_safe_dict(getattr(step, 'evidence', None))),
        'feedback': dict(_safe_dict(getattr(step, 'feedback', None))),
    }


def canonical_goal_execution_report(
    *,
    goal: str,
    business_id: str,
    tenant_id: str,
    completed: bool,
    stop_reason: str,
    steps: tuple[Any, ...] | list[Any],
    final_feedback: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    final_feedback_payload = _safe_dict(final_feedback)
    execution_feedback = dict(
        _safe_dict(final_feedback_payload.get('execution_feedback'))
        or canonical_execution_feedback(feedback=final_feedback_payload)
    )
    step_artifacts = [canonical_goal_execution_step(step) for step in tuple(steps or ())]
    return {
        'goal': _text(goal),
        'business_id': _text(business_id),
        'tenant_id': _text(tenant_id),
        'completed': bool(completed),
        'stop_reason': _text(stop_reason),
        'steps_count': len(step_artifacts),
        'attempted': bool(execution_feedback.get('attempted', step_artifacts[-1]['attempted'] if step_artifacts else False)),
        'executed': bool(execution_feedback.get('executed', step_artifacts[-1]['executed'] if step_artifacts else False)),
        'verified': bool(execution_feedback.get('verified', step_artifacts[-1]['verified'] if step_artifacts else False)),
        'operator_required': bool(execution_feedback.get('operator_required', step_artifacts[-1]['operator_required'] if step_artifacts else False)),
        'verification_status': normalize_outcome_status(
            execution_feedback.get('verification_status') or final_feedback_payload.get('verification_status'),
            verified=execution_feedback.get('verified'),
            retryable=execution_feedback.get('retryable'),
            default='unknown',
        ),
        'execution_feedback': execution_feedback,
        'final_feedback': final_feedback_payload,
        'step_artifacts': step_artifacts,
    }


def canonical_ledger_record(*, run_id: str, trace_id: str, report_artifact: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = _safe_dict(report_artifact)
    return {
        'run_id': _text(run_id),
        'trace_id': _text(trace_id),
        'goal': _text(payload.get('goal')),
        'business_id': _text(payload.get('business_id')),
        'tenant_id': _text(payload.get('tenant_id')),
        'completed': bool(payload.get('completed', False)),
        'stop_reason': _text(payload.get('stop_reason')),
        'steps_count': int(payload.get('steps_count') or len(_safe_list(payload.get('step_artifacts')))),
        'execution_feedback': dict(_safe_dict(payload.get('execution_feedback'))),
        'verification_status': _text(payload.get('verification_status')),
        'canonical_run_artifact': dict(payload),
    }


def canonical_report_builder_input(record: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _safe_dict(record)
    artifact = _safe_dict(payload.get('canonical_run_artifact'))
    if artifact:
        execution_feedback = dict(_safe_dict(artifact.get('execution_feedback')))
        return {
            **payload,
            'final_feedback': dict(_safe_dict(payload.get('final_feedback')) or _safe_dict(artifact.get('final_feedback'))),
            'execution_feedback': execution_feedback,
            'verification_status': _text(artifact.get('verification_status')),
            'steps_count': int(artifact.get('steps_count') or payload.get('steps_count') or 0),
        }
    final_feedback = _safe_dict(payload.get('final_feedback'))
    execution_feedback = dict(_safe_dict(final_feedback.get('execution_feedback')) or canonical_execution_feedback(feedback=final_feedback))
    return {
        **payload,
        'final_feedback': final_feedback,
        'execution_feedback': execution_feedback,
        'verification_status': _text(execution_feedback.get('verification_status')),
        'steps_count': int(payload.get('steps_count') or 0),
    }


__all__ = [
    'CANON_RUN_ARTIFACT_CONTRACT',
    'canonical_goal_execution_step',
    'canonical_goal_execution_report',
    'canonical_ledger_record',
    'canonical_report_builder_input',
]
