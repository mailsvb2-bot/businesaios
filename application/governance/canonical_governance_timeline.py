from __future__ import annotations

from typing import Any, Mapping

from application.governance.canonical_governance_evidence import canonical_governance_evidence
from application.effects.effect_outcome_vocabulary import normalize_outcome_status


CANON_GOVERNANCE_TIMELINE_CONTRACT = True


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _safe_list(value: object) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _text(value: object) -> str:
    return str(value or '').strip()


def canonical_baseline_snapshot(
    *,
    baseline_name: str,
    source_run_id: str = '',
    promoted_at_label: str = '',
    record: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    existing_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    existing = _safe_dict(existing_payload)
    current_record = _safe_dict(record) or _safe_dict(existing.get('record'))
    current_metadata = {**_safe_dict(existing.get('metadata')), **_safe_dict(metadata)}
    governance_evidence = _safe_dict(current_metadata.get('governance_evidence'))
    if governance_evidence:
        governance_evidence = canonical_governance_evidence(
            governance_action=_text(governance_evidence.get('governance_action') or 'promote_baseline'),
            baseline_name=_text(baseline_name or governance_evidence.get('baseline_name')),
            candidate_record=current_record,
            baseline_record=existing if existing else None,
            business_memory_summary=governance_evidence.get('business_memory_summary'),
            fit_report=governance_evidence.get('business_memory_fit'),
            scenario_alignment=governance_evidence.get('scenario_memory_alignment'),
            drift_payload=governance_evidence.get('drift'),
            rollback_payload=governance_evidence.get('rollback'),
            metadata=governance_evidence.get('metadata'),
        )
        current_metadata = {**current_metadata, 'governance_evidence': governance_evidence}
    timeline = _safe_dict(existing.get('governance_timeline'))
    rollback = _safe_dict(timeline.get('rollback'))
    return {
        'baseline_name': _text(baseline_name or existing.get('baseline_name')),
        'source_run_id': _text(source_run_id or existing.get('source_run_id') or current_record.get('run_id')),
        'goal': _text(current_record.get('goal') or existing.get('goal')),
        'business_id': _text(current_record.get('business_id') or existing.get('business_id')),
        'tenant_id': _text(current_record.get('tenant_id') or existing.get('tenant_id')),
        'promoted_at_label': _text(promoted_at_label or existing.get('promoted_at_label')),
        'metadata': current_metadata,
        'record': current_record,
        'governance_timeline': {
            'baseline_name': _text(baseline_name or existing.get('baseline_name')),
            'current_source_run_id': _text(source_run_id or existing.get('source_run_id') or current_record.get('run_id')),
            'promoted_at_label': _text(promoted_at_label or existing.get('promoted_at_label')),
            'rollback': rollback,
            'history_rows': _safe_list(timeline.get('history_rows')),
            'drift_reports': _safe_list(timeline.get('drift_reports')),
            'drift_summary': _safe_dict(timeline.get('drift_summary')),
        },
    }


def canonical_governance_history_row(
    *,
    baseline_name: str,
    event_type: str,
    source_run_id: str,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    row = _safe_dict(payload)
    timeline = _safe_dict(row.get('governance_timeline'))
    return {
        'baseline_name': _text(baseline_name or row.get('baseline_name')),
        'event_type': _text(event_type or row.get('event_type')),
        'source_run_id': _text(source_run_id or row.get('source_run_id')),
        'payload': row,
        'governance_timeline_row': {
            'baseline_name': _text(baseline_name or row.get('baseline_name')),
            'event_type': _text(event_type or row.get('event_type')),
            'source_run_id': _text(source_run_id or row.get('source_run_id')),
            'promoted_at_label': _text(row.get('promoted_at_label') or timeline.get('promoted_at_label')),
            'reason': _text(row.get('reason') or row.get('rollback_reason')),
            'metadata': _safe_dict(row.get('metadata')),
            'governance_evidence': _safe_dict(row.get('governance_evidence')),
        },
    }


def canonical_rollback_record(
    *,
    baseline_name: str,
    previous_source_run_id: str,
    new_source_run_id: str,
    reason: str,
    metadata: Mapping[str, Any] | None = None,
    existing_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    existing = _safe_dict(existing_payload)
    current_metadata = {**_safe_dict(existing.get('metadata')), **_safe_dict(metadata)}
    governance_evidence = _safe_dict(current_metadata.get('governance_evidence'))
    if governance_evidence:
        governance_evidence = canonical_governance_evidence(
            governance_action=_text(governance_evidence.get('governance_action') or 'rollback_baseline'),
            baseline_name=_text(baseline_name or governance_evidence.get('baseline_name')),
            candidate_record=None,
            baseline_record=None,
            business_memory_summary=governance_evidence.get('business_memory_summary'),
            fit_report=governance_evidence.get('business_memory_fit'),
            scenario_alignment=governance_evidence.get('scenario_memory_alignment'),
            drift_payload=governance_evidence.get('drift'),
            rollback_payload={
                'previous_source_run_id': previous_source_run_id or existing.get('previous_source_run_id'),
                'new_source_run_id': new_source_run_id or existing.get('new_source_run_id'),
                'reason': reason or existing.get('reason'),
                'metadata': current_metadata,
            },
            metadata=governance_evidence.get('metadata'),
        )
        current_metadata = {**current_metadata, 'governance_evidence': governance_evidence}
    return {
        'baseline_name': _text(baseline_name or existing.get('baseline_name')),
        'previous_source_run_id': _text(previous_source_run_id or existing.get('previous_source_run_id')),
        'new_source_run_id': _text(new_source_run_id or existing.get('new_source_run_id')),
        'reason': _text(reason or existing.get('reason')),
        'metadata': current_metadata,
        'governance_timeline': {
            'baseline_name': _text(baseline_name or existing.get('baseline_name')),
            'current_source_run_id': _text(new_source_run_id or existing.get('new_source_run_id')),
            'rollback': {
                'previous_source_run_id': _text(previous_source_run_id or existing.get('previous_source_run_id')),
                'new_source_run_id': _text(new_source_run_id or existing.get('new_source_run_id')),
                'reason': _text(reason or existing.get('reason')),
            },
        },
    }


def canonical_governance_timeline(
    *,
    baseline_name: str,
    baseline_snapshot: Mapping[str, Any] | None,
    history_rows: list[dict[str, Any]] | None,
    rollback_record: Mapping[str, Any] | None,
    drift_reports: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    baseline = canonical_baseline_snapshot(
        baseline_name=baseline_name,
        existing_payload=baseline_snapshot,
        source_run_id=_text(_safe_dict(baseline_snapshot).get('source_run_id')),
        promoted_at_label=_text(_safe_dict(baseline_snapshot).get('promoted_at_label')),
        record=_safe_dict(_safe_dict(baseline_snapshot).get('record')),
        metadata=_safe_dict(_safe_dict(baseline_snapshot).get('metadata')),
    ) if baseline_snapshot else canonical_baseline_snapshot(baseline_name=baseline_name)
    rows = [
        canonical_governance_history_row(
            baseline_name=baseline_name,
            event_type=_text(dict(row).get('event_type')),
            source_run_id=_text(dict(row).get('source_run_id')),
            payload=_safe_dict(dict(row).get('payload')),
        )
        for row in list(history_rows or [])
    ]
    rollback = None
    if rollback_record is not None:
        rollback = canonical_rollback_record(
            baseline_name=baseline_name,
            previous_source_run_id=_text(dict(rollback_record).get('previous_source_run_id')),
            new_source_run_id=_text(dict(rollback_record).get('new_source_run_id')),
            reason=_text(dict(rollback_record).get('reason')),
            metadata=_safe_dict(dict(rollback_record).get('metadata')),
            existing_payload=rollback_record,
        )
    drifts = []
    severities: list[str] = []
    for report in list(drift_reports or []):
        item = dict(report)
        severity = _text(item.get('severity') or item.get('verification_status') or 'none').lower()
        drifts.append({
            **item,
            'baseline_name': _text(item.get('baseline_name') or baseline_name),
            'candidate_run_id': _text(item.get('candidate_run_id')),
            'severity': severity,
            'verification_status': normalize_outcome_status(
                item.get('verification_status') or severity,
                verified=item.get('verified'),
                retryable=item.get('retryable'),
                default='unknown',
            ),
        })
        severities.append(severity)
    timeline = {
        'baseline_name': _text(baseline_name),
        'baseline_snapshot': baseline,
        'history_rows': rows,
        'rollback_record': rollback,
        'drift_reports': drifts,
        'drift_summary': {
            'samples': len(drifts),
            'high_count': sum(1 for s in severities if s == 'high'),
            'medium_count': sum(1 for s in severities if s == 'medium'),
            'low_count': sum(1 for s in severities if s == 'low'),
            'none_count': sum(1 for s in severities if s in {'none', '', 'unknown'}),
        },
    }
    timeline['governance_timeline'] = {
        'baseline_name': _text(baseline_name),
        'current_source_run_id': _text(baseline.get('source_run_id')),
        'promoted_at_label': _text(baseline.get('promoted_at_label')),
        'rollback': _safe_dict(rollback.get('governance_timeline', {}).get('rollback')) if rollback else {},
        'history_rows': [dict(item.get('governance_timeline_row') or {}) for item in rows],
        'drift_reports': drifts,
        'drift_summary': dict(timeline['drift_summary']),
    }
    return timeline


__all__ = [
    'CANON_GOVERNANCE_TIMELINE_CONTRACT',
    'canonical_baseline_snapshot',
    'canonical_governance_history_row',
    'canonical_governance_timeline',
    'canonical_rollback_record',
]
