from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from application.effects.canonical_execution_feedback import canonical_execution_feedback
from execution.canonical_run_artifacts import canonical_goal_execution_report
from application.effects.effect_outcome_vocabulary import normalize_outcome_status, outcome_is_verified


CANON_PERSISTENCE_VOCABULARY = True


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


def canonical_run_persistence_vocabulary(record: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = _safe_dict(record)
    run_artifact = _safe_dict(payload.get('canonical_run_artifact'))
    persisted = _safe_dict(payload.get('canonical_persistence_vocabulary'))
    final_feedback = _safe_dict(payload.get('final_feedback'))
    execution_feedback = dict(
        _safe_dict(run_artifact.get('execution_feedback'))
        or _safe_dict(final_feedback.get('execution_feedback'))
        or canonical_execution_feedback(feedback=final_feedback)
    )
    verification_status = normalize_outcome_status(
        run_artifact.get('verification_status')
        or execution_feedback.get('verification_status')
        or final_feedback.get('verification_status'),
        verified=execution_feedback.get('verified', final_feedback.get('verified')),
        retryable=execution_feedback.get('retryable', final_feedback.get('retryable')),
        default='unknown',
    )
    external_refs = (
        _safe_list(execution_feedback.get('external_refs'))
        or _safe_list(final_feedback.get('external_refs'))
        or _safe_list(run_artifact.get('external_refs'))
    )
    goal_score = final_feedback.get('goal_score')
    if goal_score in {None, ''}:
        goal_score = persisted.get('goal_score')
    if goal_score in {None, ''}:
        goal_score = _safe_dict(run_artifact.get('final_feedback')).get('goal_score')
    retry = _safe_dict(final_feedback.get('retry_classification'))
    if not retry and persisted.get('retry_kind'):
        retry = {'kind': persisted.get('retry_kind')}
    if not retry:
        retry = _safe_dict(_safe_dict(run_artifact.get('final_feedback')).get('retry_classification'))

    return {
        'tenant_id': _text(payload.get('tenant_id') or persisted.get('tenant_id') or run_artifact.get('tenant_id')),
        'business_id': _text(payload.get('business_id') or persisted.get('business_id') or run_artifact.get('business_id')),
        'run_id': _text(payload.get('run_id')),
        'trace_id': _text(payload.get('trace_id')),
        'goal': _text(payload.get('goal') or persisted.get('goal') or run_artifact.get('goal')),
        'channel': _text(payload.get('channel') or persisted.get('channel') or final_feedback.get('channel')),
        'region': _text(payload.get('region') or persisted.get('region') or final_feedback.get('region')),
        'completed': bool(payload.get('completed', persisted.get('completed', run_artifact.get('completed', False)))),
        'stop_reason': _text(payload.get('stop_reason') or persisted.get('stop_reason') or run_artifact.get('stop_reason')),
        'steps_count': int(payload.get('steps_count') or persisted.get('steps_count') or run_artifact.get('steps_count') or 0),
        'verification_status': verification_status,
        'verified': outcome_is_verified(
            verification_status,
            verified=execution_feedback.get('verified', final_feedback.get('verified')),
            retryable=execution_feedback.get('retryable', final_feedback.get('retryable')),
        ),
        'executed': bool(execution_feedback.get('executed', final_feedback.get('executed', False))),
        'attempted': bool(execution_feedback.get('attempted', final_feedback.get('attempted', False))),
        'operator_required': bool(execution_feedback.get('operator_required', final_feedback.get('operator_required', False))),
        'retryable': bool(execution_feedback.get('retryable', final_feedback.get('retryable', False))),
        'goal_score': float(goal_score or 0.0),
        'error': _text(final_feedback.get('error') or persisted.get('error') or execution_feedback.get('message')),
        'retry_kind': _text(retry.get('kind')),
        'external_refs': external_refs,
        'canonical_run_artifact': dict(run_artifact),
        'execution_feedback': execution_feedback,
        'final_feedback': final_feedback,
    }


def canonical_persistence_outcome_record(*, base_record: Mapping[str, Any] | None = None, outcome_record: Mapping[str, Any] | None = None) -> dict[str, Any]:
    base = canonical_run_persistence_vocabulary(base_record)
    outcome = _safe_dict(outcome_record)
    verification_status = normalize_outcome_status(
        outcome.get('verification_status') or base.get('verification_status'),
        verified=outcome.get('verified', base.get('verified')),
        retryable=outcome.get('retryable', base.get('retryable')),
        default='unknown',
    )
    refs = _safe_list(outcome.get('external_refs')) or list(base.get('external_refs') or [])
    return {
        'tenant_id': _text(outcome.get('tenant_id') or base.get('tenant_id')),
        'business_id': _text(outcome.get('business_id') or base.get('business_id')),
        'run_id': _text(outcome.get('run_id') or base.get('run_id')),
        'goal': _text(outcome.get('goal') or base.get('goal')),
        'step_index': int(outcome.get('step_index') or 0),
        'action_type': _text(outcome.get('action_type')),
        'action_id': _text(outcome.get('action_id')),
        'executed': bool(outcome.get('executed', base.get('executed', False))),
        'verified': outcome_is_verified(
            verification_status,
            verified=outcome.get('verified', base.get('verified')),
            retryable=outcome.get('retryable', base.get('retryable')),
        ),
        'verification_status': verification_status,
        'external_refs': refs,
        'persistence_vocabulary': {
            'verification_status': verification_status,
            'goal': _text(outcome.get('goal') or base.get('goal')),
            'run_id': _text(outcome.get('run_id') or base.get('run_id')),
            'retryable': bool(outcome.get('retryable', base.get('retryable', False))),
            'external_refs': refs,
        },
    }


def canonical_memory_record(
    *,
    tenant_id: str,
    business_id: str,
    run_id: str,
    goal: str,
    step_count: int,
    final_feedback: Mapping[str, Any] | None = None,
    canonical_run_artifact: Mapping[str, Any] | None = None,
    channel: str = '',
    region: str = '',
    completed: bool = False,
    stop_reason: str = '',
) -> dict[str, Any]:
    base = canonical_run_persistence_vocabulary(
        {
            'tenant_id': tenant_id,
            'business_id': business_id,
            'run_id': run_id,
            'goal': goal,
            'channel': channel,
            'region': region,
            'completed': completed,
            'stop_reason': stop_reason,
            'steps_count': step_count,
            'final_feedback': dict(_safe_dict(final_feedback)),
            'canonical_run_artifact': dict(_safe_dict(canonical_run_artifact)),
        }
    )
    return {
        'tenant_id': _text(tenant_id),
        'business_id': _text(business_id),
        'run_id': _text(run_id),
        'goal': _text(goal),
        'step_count': int(step_count),
        'channel': _text(channel),
        'region': _text(region),
        'verification_status': _text(base.get('verification_status')),
        'goal_score': float(base.get('goal_score') or 0.0),
        'completed': bool(base.get('completed', completed)),
        'stop_reason': _text(base.get('stop_reason') or stop_reason),
        'persistence_vocabulary': {
            'verification_status': _text(base.get('verification_status')),
            'goal_score': float(base.get('goal_score') or 0.0),
            'retry_kind': _text(base.get('retry_kind')),
            'error': _text(base.get('error')),
            'external_refs': list(base.get('external_refs') or []),
        },
    }


__all__ = [
    'CANON_PERSISTENCE_VOCABULARY',
    'canonical_memory_record',
    'canonical_persistence_outcome_record',
    'canonical_run_persistence_vocabulary',
]
