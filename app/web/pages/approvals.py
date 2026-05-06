from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from app.web.components import ApprovalQueueCard
from core.tenancy.normalization import require_tenant_id
from governance.approval_contract import ApprovalStoreContract
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_APPROVALS_PAGE = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _row_subject_fingerprint(row: Mapping[str, Any]) -> str:
    return str(row.get('subject_fingerprint') or _safe_dict(row.get('metadata')).get('subject_fingerprint') or '').strip()


def _operator_action(row: Mapping[str, Any]) -> dict[str, Any]:
    metadata = _safe_dict(row.get('metadata'))
    return {
        'approval_id': str(row.get('approval_id') or '').strip() or None,
        'decision_id': str(metadata.get('decision_id') or row.get('decision_id') or '').strip() or None,
        'action_name': str(metadata.get('action_name') or row.get('action_name') or '').strip() or None,
        'subject_fingerprint': _row_subject_fingerprint(row) or None,
        'status': str(row.get('status') or '').strip() or None,
        'dual_control': _safe_int(row.get('min_distinct_approvers', 1), default=1) > 1,
        'expires_at': row.get('expires_at'),
    }




def _audit_recent_event_count(audit_payload: Mapping[str, Any], event_type: str) -> int:
    recent = tuple(_safe_dict(audit_payload).get('recent_events', ()) or ())
    return sum(1 for item in recent if str(_safe_dict(item).get('event_type') or '').strip() == str(event_type).strip())


def _timeline_sort_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    item = _safe_dict(row)
    return (
        str(item.get('emitted_at') or '').strip(),
        str(item.get('ref_id') or '').strip(),
        str(item.get('status') or '').strip(),
    )


def _merge_timelines(*timelines: object, limit: int = 25) -> tuple[dict[str, Any], ...]:
    merged: list[dict[str, Any]] = []
    for timeline in timelines:
        for row in tuple(timeline or ()):
            merged.append(_safe_dict(row))
    merged.sort(key=_timeline_sort_key, reverse=True)
    return tuple(merged[: max(0, int(limit))])


def _override_operator_action(row: Mapping[str, Any]) -> dict[str, Any]:
    metadata = _safe_dict(row.get('metadata'))
    decision = _safe_dict(row.get('decision'))
    return {
        'override_id': str(row.get('override_id') or '').strip() or None,
        'execution_id': str(row.get('execution_id') or '').strip() or None,
        'decision_id': str(row.get('decision_id') or '').strip() or None,
        'action_name': str(row.get('action_name') or '').strip() or None,
        'subject_fingerprint': str(row.get('subject_fingerprint') or '').strip() or None,
        'status': str(row.get('status') or '').strip() or None,
        'expires_at': row.get('expires_at'),
        'impact_category': str(metadata.get('impact_category') or '').strip() or None,
        'decision_resolution': str(decision.get('resolution') or '').strip() or None,
    }


@dataclass(frozen=True, slots=True)
class ApprovalsPage:
    approval_queue_card: ApprovalQueueCard = field(default_factory=ApprovalQueueCard)
    kind: str = 'approvals_page'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        queue = _safe_dict(normalized.get('queue'))
        queue_payload = _safe_dict(queue.get('payload')) if queue.get('kind') else queue
        rows = tuple(queue_payload.get('rows', ()) or ())
        override_queue = _safe_dict(normalized.get('operator_overrides'))
        override_rows = tuple(override_queue.get('records', ()) or ())
        execution_rows = tuple(item for item in rows if str(item.get('subject_type') or '') == 'action_execution')
        audit_payload = _safe_dict(normalized.get('audit') or queue_payload.get('audit') or override_queue.get('audit'))
        timeline = _merge_timelines(queue_payload.get('timeline'), override_queue.get('timeline'))
        execution_pending = tuple(item for item in execution_rows if str(item.get('status') or '') == 'requested')
        fingerprint_bound_count = sum(1 for item in execution_pending if _row_subject_fingerprint(item))
        queue_summary = _safe_dict(queue_payload.get('summary'))
        override_summary = _safe_dict(override_queue.get('summary'))
        dual_control_count = _safe_int(queue_summary.get('dual_control_count'), default=sum(1 for item in rows if _safe_int(item.get('min_distinct_approvers', 1), default=1) > 1))
        operator_actions = tuple(_operator_action(item) for item in execution_pending[:25])
        override_actions = tuple(_override_operator_action(item) for item in override_rows[:25])
        status_counts = {
            'requested': _safe_int(_safe_dict(queue_summary.get('lifecycle_counts')).get('requested'), default=sum(1 for item in rows if str(item.get('status') or '') == 'requested')),
            'approved': _safe_int(_safe_dict(queue_summary.get('lifecycle_counts')).get('approved'), default=sum(1 for item in rows if str(item.get('status') or '') == 'approved')),
            'rejected': _safe_int(_safe_dict(queue_summary.get('lifecycle_counts')).get('rejected'), default=sum(1 for item in rows if str(item.get('status') or '') == 'rejected')),
            'expired': _safe_int(_safe_dict(queue_summary.get('lifecycle_counts')).get('expired'), default=sum(1 for item in rows if str(item.get('status') or '') == 'expired')),
            'cancelled': _safe_int(_safe_dict(queue_summary.get('lifecycle_counts')).get('cancelled'), default=sum(1 for item in rows if str(item.get('status') or '') == 'cancelled')),
            'consumed': _safe_int(_safe_dict(override_summary.get('lifecycle_counts')).get('consumed'), default=_safe_int(_safe_dict(queue_summary.get('lifecycle_counts')).get('consumed'), default=0)),
        }
        resume_candidate_count = (_safe_int(queue_summary.get('resume_candidate_count'), default=sum(1 for item in rows if str(item.get('status') or '') == 'approved')) + _safe_int(override_summary.get('resume_candidate_count'), default=sum(1 for item in override_rows if str(_safe_dict(item.get('decision')).get('resolution') or '') == 'approve_once')))
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'title': 'Approvals',
                'queue': queue or None,
                'tenant_bound': True,
                'queue_actions': operator_actions,
                'operator_overrides': override_queue or None,
                'override_actions': override_actions,
                'audit': audit_payload or None,
                'timeline': timeline,
                'operator_console': {
                    'action_required': len(operator_actions) > 0 or len(override_actions) > 0,
                    'pending_execution_approvals': len(execution_pending),
                    'dual_control_execution_count': sum(1 for item in execution_pending if _safe_int(item.get('min_distinct_approvers', 1), default=1) > 1),
                    'pending_operator_overrides': len(override_rows),
                    'expiring_operator_overrides': sum(1 for item in override_rows if bool(item.get('expires_at'))),
                    'resume_candidate_count': resume_candidate_count,
                    'resume_ready_event_count': _safe_int(_safe_dict(audit_payload.get('lifecycle_counts')).get('resume_ready'), default=_audit_recent_event_count(audit_payload, 'governance_execution_resume_ready')) if audit_payload else 0,
                    'audit_integrity_valid': bool(_safe_dict(audit_payload.get('integrity')).get('valid', False)) if audit_payload else False,
                    'timeline_count': len(timeline),
                    'last_timeline_status': str(_safe_dict(timeline[0]).get('status') or '').strip() if timeline else None,
                },
                'summary': {
                    'total_count': len(rows),
                    'execution_pending_count': len(execution_pending),
                    'fingerprint_bound_count': fingerprint_bound_count,
                    'action_bound_count': sum(1 for item in execution_pending if str(_safe_dict(item.get('metadata')).get('action_name') or item.get('action_name') or '').strip()),
                    'decision_bound_count': sum(1 for item in execution_pending if str(_safe_dict(item.get('metadata')).get('decision_id') or item.get('decision_id') or '').strip()),
                    'dual_control_count': dual_control_count,
                    'history_count': _safe_int(queue_summary.get('history_count'), default=len(rows)) + _safe_int(override_summary.get('history_count'), default=len(override_rows)),
                    'expiring_count': _safe_int(queue_summary.get('expiring_count'), default=sum(1 for item in rows if bool(item.get('expires_at')))),
                    'status_counts': status_counts,
                    'operator_actionable_count': len(operator_actions),
                    'open_override_count': len(override_rows),
                    'override_actionable_count': len(override_actions),
                    'override_fingerprint_bound_count': sum(1 for item in override_rows if str(item.get('subject_fingerprint') or '').strip()),
                    'override_decided_count': sum(1 for item in override_rows if str(item.get('decision_resolution') or _safe_dict(item.get('decision')).get('resolution') or '').strip()),
                    'resume_candidate_count': resume_candidate_count,
                    'resume_ready_event_count': _safe_int(_safe_dict(audit_payload.get('lifecycle_counts')).get('resume_ready'), default=_audit_recent_event_count(audit_payload, 'governance_execution_resume_ready')) if audit_payload else 0,
                    'audit_integrity_valid': bool(_safe_dict(audit_payload.get('integrity')).get('valid', False)) if audit_payload else False,
                    'audit_event_count': _safe_int(_safe_dict(audit_payload.get('integrity')).get('event_count'), default=_safe_int(audit_payload.get('count'), default=0)) if audit_payload else 0,
                    'timeline_count': len(timeline),
                    'last_timeline_status': str(_safe_dict(timeline[0]).get('status') or '').strip() if timeline else None,
                },
            },
        )

    def build_from_store(
        self,
        *,
        tenant_id: str,
        approval_store: ApprovalStoreContract,
        status_filter: tuple[str, ...] = (),
        subject_type: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        queue = self.approval_queue_card.build_from_records(
            tenant_id=required_tenant_id,
            records=approval_store.list_open(tenant_id=required_tenant_id),
            status_filter=status_filter,
            subject_type=subject_type,
            limit=limit,
        )
        return self.build({'tenant_id': required_tenant_id, 'queue': queue})


__all__ = ['ApprovalsPage', 'CANON_WEB_APPROVALS_PAGE']
