from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from governance.control_plane_audit_log import GovernanceAuditEvent, GovernanceAuditLogContract


def safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def text(value: object, *, default: str = '') -> str:
    rendered = str(value or '').strip()
    return rendered or default


def safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_iso(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat() if value.tzinfo is not None else None
    rendered = text(value)
    return rendered or None


def timestamp_sort_value(*values: object) -> str:
    best = ''
    for value in values:
        rendered = text(value)
        if rendered and rendered > best:
            best = rendered
    return best


def lifecycle_counts(records: tuple[Mapping[str, Any], ...], *, status_key: str = 'status') -> dict[str, int]:
    counts = {'requested': 0, 'approved': 0, 'rejected': 0, 'expired': 0, 'cancelled': 0, 'consumed': 0}
    for item in records:
        status = text(item.get(status_key)).lower()
        if status in counts:
            counts[status] += 1
    return counts


def resume_hint(item: Mapping[str, Any]) -> dict[str, object]:
    metadata = safe_dict(item.get('metadata'))
    return {
        'execution_id': text(item.get('subject_id') or item.get('execution_id')) or None,
        'decision_id': text(item.get('decision_id') or metadata.get('decision_id')) or None,
        'action_name': text(item.get('action_name') or metadata.get('action_name')) or None,
        'approval_id': text(item.get('approval_id')) or None,
        'override_id': text(item.get('override_id')) or None,
        'subject_fingerprint': text(item.get('subject_fingerprint') or metadata.get('subject_fingerprint')) or None,
        'resume_ready': text(item.get('status')) in {'approved'} or text(safe_dict(item.get('decision')).get('resolution')) in {'approve_once'},
    }


def latest_records(
    records: tuple[Mapping[str, Any], ...],
    *,
    limit: int = 50,
    timestamp_keys: tuple[str, ...] = ('created_at', 'requested_at', 'expires_at', 'consumed_at'),
) -> tuple[Mapping[str, Any], ...]:
    ranked = sorted(
        records,
        key=lambda item: (
            timestamp_sort_value(*(safe_dict(item).get(key) for key in timestamp_keys)),
            text(safe_dict(item).get('approval_id') or safe_dict(item).get('override_id')),
        ),
        reverse=True,
    )
    return tuple(ranked[: max(0, int(limit))])


def build_control_plane_timeline(
    *,
    approvals: tuple[Mapping[str, Any], ...],
    overrides: tuple[Mapping[str, Any], ...],
    audit_summary: Mapping[str, Any],
    limit: int = 25,
) -> tuple[dict[str, object], ...]:
    items: list[dict[str, object]] = []
    for item in approvals:
        row = safe_dict(item)
        decisions = tuple(row.get('decisions', ()) or ())
        last_decision = safe_dict(decisions[-1]) if decisions else {}
        items.append({
            'kind': 'approval',
            'ref_id': text(row.get('approval_id')) or None,
            'tenant_id': text(row.get('tenant_id')) or None,
            'status': text(row.get('status')) or None,
            'action_name': text(row.get('action_name') or safe_dict(row.get('metadata')).get('action_name')) or None,
            'decision_id': text(row.get('decision_id') or safe_dict(row.get('metadata')).get('decision_id')) or None,
            'subject_fingerprint': text(row.get('subject_fingerprint') or safe_dict(row.get('metadata')).get('subject_fingerprint')) or None,
            'emitted_at': timestamp_sort_value(last_decision.get('decided_at'), row.get('expires_at'), row.get('created_at')) or None,
        })
    for item in overrides:
        row = safe_dict(item)
        decision = safe_dict(row.get('decision'))
        items.append({
            'kind': 'operator_override',
            'ref_id': text(row.get('override_id')) or None,
            'tenant_id': text(row.get('tenant_id')) or None,
            'status': text(row.get('status')) or None,
            'action_name': text(row.get('action_name')) or None,
            'decision_id': text(row.get('decision_id')) or None,
            'subject_fingerprint': text(row.get('subject_fingerprint')) or None,
            'emitted_at': timestamp_sort_value(row.get('consumed_at'), decision.get('decided_at'), row.get('expires_at'), row.get('requested_at')) or None,
        })
    for item in tuple(safe_dict(audit_summary).get('recent_events', ()) or ()):
        row = safe_dict(item)
        payload = safe_dict(row.get('payload'))
        items.append({
            'kind': 'audit_event',
            'ref_id': None,
            'tenant_id': text(payload.get('tenant_id')) or None,
            'status': text(row.get('event_type')) or None,
            'action_name': text(payload.get('action_name')) or None,
            'decision_id': text(payload.get('decision_id')) or None,
            'subject_fingerprint': text(safe_dict(payload.get('approval')).get('subject_fingerprint') or safe_dict(payload.get('resume')).get('subject_fingerprint')) or None,
            'emitted_at': safe_iso(row.get('emitted_at')),
        })
    kind_priority = {'approval': 3, 'operator_override': 2, 'audit_event': 1}
    items.sort(
        key=lambda item: (
            1 if (text(item.get('decision_id')) or text(item.get('subject_fingerprint')) or text(item.get('ref_id'))) else 0,
            kind_priority.get(text(item.get('kind')), 0),
            timestamp_sort_value(item.get('emitted_at')),
            text(item.get('ref_id')),
            text(item.get('status')),
        ),
        reverse=True,
    )
    return tuple(items[: max(0, int(limit))])


def list_tenant_records(store: object, *, tenant_id: str, include_terminal: bool = True) -> tuple[Any, ...]:
    list_for_tenant = getattr(store, 'list_for_tenant', None)
    if callable(list_for_tenant):
        return tuple(list_for_tenant(tenant_id=tenant_id, include_terminal=include_terminal))
    if include_terminal:
        items = tuple(getattr(store, '_items', {}).values())
        return tuple(item for item in items if text(getattr(getattr(item, 'request', None), 'tenant_id', '')) == text(tenant_id))
    list_open = getattr(store, 'list_open', None)
    if callable(list_open):
        return tuple(list_open(tenant_id=tenant_id))
    return ()


def resume_candidates(records: tuple[Mapping[str, Any], ...]) -> tuple[dict[str, object], ...]:
    candidates: list[dict[str, object]] = []
    for item in records:
        hint = resume_hint(item)
        if hint.get('resume_ready'):
            candidates.append(hint)
    return tuple(candidates)


def route_action_summary(item: Mapping[str, Any]) -> dict[str, object]:
    metadata = safe_dict(item.get('metadata'))
    return {
        'approval_id': text(item.get('approval_id')) or None,
        'subject_type': text(item.get('subject_type')) or None,
        'subject_id': text(item.get('subject_id')) or None,
        'decision_id': text(item.get('decision_id') or metadata.get('decision_id')) or None,
        'action_name': text(item.get('action_name') or metadata.get('action_name')) or None,
        'subject_fingerprint': text(item.get('subject_fingerprint') or metadata.get('subject_fingerprint')) or None,
        'status': text(item.get('status')) or None,
        'expires_at': safe_iso(item.get('expires_at')),
        'dual_control': safe_int(item.get('min_distinct_approvers', 1), default=1) > 1,
    }


def audit_payload_summary(audit_log: GovernanceAuditLogContract, *, tenant_id: str) -> dict[str, object]:
    summary = audit_log.summarize_tenant_lifecycle(tenant_id, limit=200)
    recent_events = tuple(summary.get('recent_events', ()) or ())
    integrity = safe_dict(summary.get('integrity'))
    return {
        'count': safe_int(summary.get('count'), default=len(recent_events)),
        'lifecycle_counts': safe_dict(summary.get('lifecycle_counts')),
        'recent_events': recent_events,
        'integrity': {
            'checked': bool(integrity.get('checked', False)),
            'valid': bool(integrity.get('valid', False)),
            'event_count': safe_int(integrity.get('event_count'), default=safe_int(summary.get('count'), default=0)),
            'chain_head': text(integrity.get('chain_head')) or None,
            'error': text(integrity.get('error')) or None,
        },
    }


def append_control_plane_audit(
    audit_log: GovernanceAuditLogContract,
    *,
    tenant_id: str,
    event_type: str,
    payload: Mapping[str, object],
) -> None:
    audit_log.append(
        GovernanceAuditEvent(
            event_type=text(event_type),
            tenant_id=text(tenant_id),
            payload=dict(payload),
        )
    )


def override_record_dict(record: Any) -> dict[str, Any]:
    request = getattr(record, 'request', None)
    decision = getattr(record, 'decision', None)
    metadata = dict(getattr(request, 'metadata', {}) or {})
    return {
        'override_id': request.override_id,
        'tenant_id': request.tenant_id,
        'execution_id': request.execution_id,
        'decision_id': request.decision_id,
        'action_name': request.action_name,
        'requested_by': request.requested_by,
        'reason': request.reason,
        'subject_fingerprint': request.subject_fingerprint,
        'status': record.status.value,
        'final_reason': record.final_reason,
        'requested_at': safe_iso(request.requested_at),
        'expires_at': safe_iso(request.expires_at),
        'metadata': metadata,
        'decision': {
            'actor_id': getattr(decision, 'actor_id', None),
            'role_id': getattr(getattr(decision, 'role_id', None), 'value', None),
            'resolution': getattr(getattr(decision, 'resolution', None), 'value', None),
            'note': getattr(decision, 'note', None),
            'decided_at': safe_iso(getattr(decision, 'decided_at', None)),
            'metadata': dict(getattr(decision, 'metadata', {}) or {}),
        } if decision is not None else None,
        'consumed_at': safe_iso(getattr(record, 'consumed_at', None)),
        'consumed_by_execution_id': getattr(record, 'consumed_by_execution_id', None),
    }


def override_action_summary(item: Mapping[str, Any]) -> dict[str, object]:
    metadata = safe_dict(item.get('metadata'))
    decision = safe_dict(item.get('decision'))
    return {
        'override_id': text(item.get('override_id')) or None,
        'execution_id': text(item.get('execution_id')) or None,
        'decision_id': text(item.get('decision_id')) or None,
        'action_name': text(item.get('action_name')) or None,
        'subject_fingerprint': text(item.get('subject_fingerprint')) or None,
        'status': text(item.get('status')) or None,
        'expires_at': safe_iso(item.get('expires_at')),
        'requested_by': text(item.get('requested_by')) or None,
        'impact_category': text(metadata.get('impact_category')) or None,
        'decision_resolution': text(decision.get('resolution')) or None,
    }


def record_dict(record: Any) -> dict[str, Any]:
    request = getattr(record, 'request', None)
    metadata = dict(getattr(request, 'metadata', {}) or {})
    return {
        'approval_id': request.approval_id,
        'tenant_id': request.tenant_id,
        'subject_type': request.subject_type,
        'subject_id': request.subject_id,
        'requested_by': request.requested_by,
        'reason': request.reason,
        'status': record.status.value,
        'final_reason': record.final_reason,
        'required_role_groups': [[role.value for role in group] for group in request.required_role_groups],
        'min_distinct_approvers': request.min_distinct_approvers,
        'prohibit_self_approval': request.prohibit_self_approval,
        'created_at': request.created_at.isoformat(),
        'expires_at': None if request.expires_at is None else request.expires_at.isoformat(),
        'metadata': metadata,
        'subject_fingerprint': text(metadata.get('subject_fingerprint')) or None,
        'decision_id': text(metadata.get('decision_id')) or None,
        'action_name': text(metadata.get('action_name')) or None,
        'approval_kind': text(metadata.get('approval_kind')) or None,
        'decisions': [
            {
                'actor_id': item.actor_id,
                'role_id': item.role_id.value,
                'outcome': item.outcome.value,
                'rationale': item.rationale,
                'decided_at': item.decided_at.isoformat(),
                'metadata': dict(item.metadata),
            }
            for item in record.decisions
        ],
    }
