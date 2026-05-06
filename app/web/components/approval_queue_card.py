from __future__ import annotations

"""Tenant-bound approval queue card.

Thin operator-console renderer only.
It never decides approval outcomes and never bypasses governance.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping

from core.tenancy.normalization import normalize_tenant_id, require_tenant_id
from security.payload_redaction import PayloadRedactor
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_APPROVAL_QUEUE_CARD = True
_MAX_LIMIT = 500


def _safe_int(value: Any, *, default: int = 0, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value or '').strip()
    return text or None


def _enum_value(value: Any) -> str:
    return str(getattr(value, 'value', value) or '').strip()


def _mapping_copy(value: Any) -> dict[str, Any]:
    return {str(k): v for k, v in dict(value or {}).items()} if isinstance(value, Mapping) else {}


def _approval_row(record: Any) -> dict[str, Any]:
    request = getattr(record, 'request', record)
    decisions = tuple(getattr(record, 'decisions', ()) or ())
    required_groups = tuple(getattr(request, 'required_role_groups', ()) or ())
    status = _enum_value(getattr(record, 'status', ''))
    return {
        'approval_id': str(getattr(request, 'approval_id', '') or '').strip(),
        'tenant_id': str(getattr(request, 'tenant_id', getattr(record, 'tenant_id', '')) or '').strip(),
        'subject_type': str(getattr(request, 'subject_type', '') or '').strip(),
        'subject_id': str(getattr(request, 'subject_id', '') or '').strip(),
        'requested_by': str(getattr(request, 'requested_by', '') or '').strip(),
        'reason': str(getattr(request, 'reason', '') or '').strip(),
        'status': status,
        'created_at': _iso(getattr(request, 'created_at', None)),
        'expires_at': _iso(getattr(request, 'expires_at', None)),
        'decision_count': len(decisions),
        'required_groups': tuple(
            tuple(_enum_value(role) for role in tuple(group or ()))
            for group in required_groups
            if tuple(group or ())
        ),
        'min_distinct_approvers': _safe_int(getattr(request, 'min_distinct_approvers', 1), default=1, minimum=1),
        'prohibit_self_approval': bool(getattr(request, 'prohibit_self_approval', True)),
        'final_reason': str(getattr(record, 'final_reason', '') or '').strip() or None,
        'metadata': _mapping_copy(getattr(request, 'metadata', {})),
        'is_expiring': bool(getattr(request, 'expires_at', None)),
    }


@dataclass(frozen=True, slots=True)
class ApprovalQueueCard:
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    kind: str = 'approval_queue_card'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        rows: list[dict[str, Any]] = []
        for item in tuple(normalized.get('rows', ()) or ()):
            row = dict(item or {})
            row_tenant_id = normalize_tenant_id(row.get('tenant_id'))
            if row_tenant_id and row_tenant_id != tenant_id:
                continue
            row['tenant_id'] = tenant_id
            rows.append(row)
        rows.sort(key=lambda item: (str(item.get('status') or ''), str(item.get('created_at') or ''), str(item.get('approval_id') or '')))
        result = {
            'tenant_id': tenant_id,
            'count': len(rows),
            'rows': tuple(rows),
            'empty': len(rows) == 0,
            'filters': {
                'status': tuple(str(x) for x in tuple(normalized.get('status_filter', ()) or ()) if str(x).strip()),
                'subject_type': str(normalized.get('subject_type') or '').strip(),
            },
            'summary': {
                'requested_count': sum(1 for row in rows if str(row.get('status') or '') == 'requested'),
                'approved_count': sum(1 for row in rows if str(row.get('status') or '') == 'approved'),
                'rejected_count': sum(1 for row in rows if str(row.get('status') or '') == 'rejected'),
                'expiring_count': sum(1 for row in rows if bool(row.get('is_expiring'))),
            },
            'tenant_bound': True,
        }
        return build_kinded_payload(self.kind, self.payload_redactor.redact(result))

    def build_from_records(
        self,
        *,
        tenant_id: str,
        records: Iterable[Any],
        status_filter: Iterable[str] | None = None,
        subject_type: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        allowed_statuses = {str(item).strip() for item in tuple(status_filter or ()) if str(item).strip()}
        normalized_subject_type = str(subject_type or '').strip()
        normalized_limit = _safe_int(limit, default=50, minimum=1, maximum=_MAX_LIMIT)
        rows: list[dict[str, Any]] = []
        for record in records:
            row = _approval_row(record)
            row_tenant_id = normalize_tenant_id(row.get('tenant_id'))
            if row_tenant_id and row_tenant_id != required_tenant_id:
                continue
            row['tenant_id'] = required_tenant_id
            if allowed_statuses and str(row.get('status') or '') not in allowed_statuses:
                continue
            if normalized_subject_type and str(row.get('subject_type') or '') != normalized_subject_type:
                continue
            rows.append(row)
            if len(rows) >= normalized_limit:
                break
        return self.build(
            {
                'tenant_id': required_tenant_id,
                'rows': tuple(rows),
                'status_filter': tuple(sorted(allowed_statuses)),
                'subject_type': normalized_subject_type,
            }
        )


__all__ = ['ApprovalQueueCard', 'CANON_WEB_APPROVAL_QUEUE_CARD']
