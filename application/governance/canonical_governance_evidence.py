from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from application.effects.effect_outcome_vocabulary import normalize_outcome_status
from execution.business_operating_memory import project_business_memory_governance_summary
from execution.canonical_persistence_vocabulary import canonical_run_persistence_vocabulary

CANON_GOVERNANCE_EVIDENCE_CONTRACT = True


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


def _memory_summary(summary: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = project_business_memory_governance_summary(_safe_dict(summary))
    return {
        'tenant_id': _text(payload.get('tenant_id')),
        'business_id': _text(payload.get('business_id')),
        'business_profile': dict(_safe_dict(payload.get('business_profile'))),
        'total_runs': int(payload.get('total_runs') or 0),
        'completed_runs': int(payload.get('completed_runs') or 0),
        'failed_runs': int(payload.get('failed_runs') or 0),
        'average_goal_score': float(payload.get('average_goal_score') or 0.0),
        'active_goals': _safe_list(payload.get('active_goals')),
        'recurring_failures': _safe_list(payload.get('recurring_failures')),
        'recurring_wins': _safe_list(payload.get('recurring_wins')),
        'anti_patterns': _safe_list(payload.get('anti_patterns')),
        'learned_preferences': dict(_safe_dict(payload.get('learned_preferences'))),
        'operating_constraints': dict(_safe_dict(payload.get('operating_constraints'))),
        'trends': dict(_safe_dict(payload.get('trends'))),
    }


def _memory_fit(fit_report: object | Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _safe_dict(fit_report) if isinstance(fit_report, Mapping) else {}
    approved = payload.get('approved')
    if approved is None:
        approved = getattr(fit_report, 'approved', False)
    score = payload.get('score')
    if score in {None, ''}:
        score = getattr(fit_report, 'score', 0.0)
    reasons = payload.get('reasons')
    if reasons is None:
        reasons = getattr(fit_report, 'reasons', ())
    summary = payload.get('summary')
    if summary in {None, ''}:
        summary = getattr(fit_report, 'summary', '')
    return {
        'approved': bool(approved),
        'score': float(score or 0.0),
        'reasons': _safe_list(reasons),
        'summary': _text(summary),
    }


def _scenario_alignment(alignment: object | Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _safe_dict(alignment) if isinstance(alignment, Mapping) else {}
    if not payload and alignment is None:
        return {'scenario': '', 'aligned': False, 'score': 0.0, 'reasons': []}
    scenario = payload.get('scenario') if payload else getattr(alignment, 'scenario', '')
    aligned = payload.get('aligned') if payload else getattr(alignment, 'aligned', False)
    score = payload.get('score') if payload else getattr(alignment, 'score', 0.0)
    reasons = payload.get('reasons') if payload else getattr(alignment, 'reasons', ())
    return {
        'scenario': _text(scenario),
        'aligned': bool(aligned),
        'score': float(score or 0.0),
        'reasons': _safe_list(reasons),
    }


def _drift_payload(drift_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _safe_dict(drift_payload)
    status = normalize_outcome_status(
        payload.get('verification_status') or payload.get('status') or payload.get('severity'),
        verified=payload.get('verified'),
        retryable=payload.get('retryable'),
        default='unknown',
    )
    return {
        'severity': _text(payload.get('severity')),
        'goal_score_delta': float(payload.get('goal_score_delta') or 0.0),
        'changed_fields': _safe_list(payload.get('changed_fields')),
        'left_only_events': _safe_list(payload.get('left_only_events')),
        'right_only_events': _safe_list(payload.get('right_only_events')),
        'verification_status': status,
        'report_text': _text(payload.get('report_text')),
    }


def _rollback_payload(rollback_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _safe_dict(rollback_payload)
    return {
        'previous_source_run_id': _text(payload.get('previous_source_run_id')),
        'new_source_run_id': _text(payload.get('new_source_run_id')),
        'reason': _text(payload.get('reason') or payload.get('rollback_reason')),
        'metadata': dict(_safe_dict(payload.get('metadata'))),
    }


def canonical_governance_evidence(
    *,
    governance_action: str,
    baseline_name: str = '',
    candidate_record: Mapping[str, Any] | None = None,
    baseline_record: Mapping[str, Any] | None = None,
    business_memory_summary: Mapping[str, Any] | None = None,
    fit_report: object | Mapping[str, Any] | None = None,
    scenario_alignment: object | Mapping[str, Any] | None = None,
    drift_payload: Mapping[str, Any] | None = None,
    rollback_payload: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    candidate = canonical_run_persistence_vocabulary(candidate_record)
    baseline_payload = _safe_dict(baseline_record)
    baseline_candidate = canonical_run_persistence_vocabulary(
        baseline_payload.get('record') if isinstance(baseline_payload.get('record'), Mapping) else baseline_payload
    ) if baseline_payload else canonical_run_persistence_vocabulary({})
    memory = _memory_summary(business_memory_summary)
    fit = _memory_fit(fit_report)
    alignment = _scenario_alignment(scenario_alignment)
    drift = _drift_payload(drift_payload)
    rollback = _rollback_payload(rollback_payload)

    evidence = {
        'governance_action': _text(governance_action),
        'baseline_name': _text(baseline_name or baseline_payload.get('baseline_name')),
        'candidate_run_id': _text(candidate.get('run_id')),
        'baseline_run_id': _text(baseline_payload.get('source_run_id') or baseline_candidate.get('run_id')),
        'tenant_id': _text(candidate.get('tenant_id') or baseline_candidate.get('tenant_id') or memory.get('tenant_id')),
        'business_id': _text(candidate.get('business_id') or baseline_candidate.get('business_id') or memory.get('business_id')),
        'goal': _text(candidate.get('goal') or baseline_candidate.get('goal')),
        'verification_status': _text(candidate.get('verification_status') or drift.get('verification_status')),
        'business_memory_summary': memory,
        'business_memory_fit': fit,
        'scenario_memory_alignment': alignment,
        'drift': drift,
        'rollback': rollback,
        'candidate_persistence_vocabulary': candidate,
        'baseline_persistence_vocabulary': baseline_candidate,
        'metadata': dict(_safe_dict(metadata)),
        'summary': {
            'approved': bool(fit.get('approved', False)),
            'verification_status': _text(candidate.get('verification_status') or drift.get('severity') or 'unknown'),
            'scenario_aligned': bool(alignment.get('aligned', False)),
            'has_drift_signal': bool(drift.get('severity')),
            'has_rollback_signal': bool(rollback.get('reason')),
        },
    }
    return evidence


def governance_evidence_roundtrip(*, expected_memory_summary: Mapping[str, Any] | None, governance_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _safe_dict(governance_payload)
    evidence = _safe_dict(payload.get('governance_evidence')) or payload
    observed_summary = _memory_summary(evidence.get('business_memory_summary'))
    expected = _memory_summary(expected_memory_summary)
    ok = (
        expected.get('tenant_id') == observed_summary.get('tenant_id')
        and expected.get('business_id') == observed_summary.get('business_id')
        and int(expected.get('total_runs') or 0) == int(observed_summary.get('total_runs') or 0)
    )
    return {
        'ok': ok,
        'expected': expected,
        'observed': observed_summary,
        'governance_action': _text(evidence.get('governance_action')),
        'baseline_name': _text(evidence.get('baseline_name')),
        'candidate_run_id': _text(evidence.get('candidate_run_id')),
    }


__all__ = [
    'CANON_GOVERNANCE_EVIDENCE_CONTRACT',
    'canonical_governance_evidence',
    'governance_evidence_roundtrip',
]
