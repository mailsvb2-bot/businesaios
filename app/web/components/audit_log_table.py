from __future__ import annotations

"""Redacted audit log table for operator/admin web surfaces."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping

from core.tenancy.normalization import normalize_tenant_id, require_tenant_id
from security.audit_redaction_policy import AuditRedactionPolicy
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_AUDIT_LOG_TABLE = True
_MAX_LIMIT = 1000


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


def _row_from_event(event: Any, policy: AuditRedactionPolicy) -> dict[str, Any]:
    raw = {
        'audit_id': str(getattr(event, 'audit_id', getattr(event, 'event_id', '')) or '').strip(),
        'tenant_id': str(getattr(event, 'tenant_id', '') or '').strip(),
        'event_type': str(getattr(event, 'event_type', '') or '').strip(),
        'category': _enum_value(getattr(event, 'category', '')),
        'severity': _enum_value(getattr(event, 'severity', '')),
        'emitted_at': _iso(getattr(event, 'emitted_at', None)),
        'actor_id': getattr(event, 'actor_id', None),
        'source_component': getattr(event, 'source_component', None),
        'source_namespace': getattr(event, 'source_namespace', None),
        'trace_id': getattr(event, 'trace_id', None),
        'run_id': getattr(event, 'run_id', None),
        'decision_id': getattr(event, 'decision_id', None),
        'action_id': getattr(event, 'action_id', None),
        'correlation_id': getattr(event, 'correlation_id', None),
        'subject_type': getattr(event, 'subject_type', None),
        'subject_id': getattr(event, 'subject_id', None),
        'tags': tuple(str(x) for x in tuple(getattr(event, 'tags', ()) or ())),
        'payload': dict(getattr(event, 'payload', {}) or {}),
        'metadata': dict(getattr(event, 'metadata', {}) or {}),
    }
    return policy.redact_event_dict(raw)


@dataclass(frozen=True, slots=True)
class AuditLogTable:
    audit_redaction_policy: AuditRedactionPolicy = field(default_factory=AuditRedactionPolicy)
    kind: str = 'audit_log_table'

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
        rows.sort(key=lambda item: (str(item.get('emitted_at') or ''), str(item.get('audit_id') or '')), reverse=True)
        result = {
            'tenant_id': tenant_id,
            'count': len(rows),
            'rows': tuple(rows),
            'columns': (
                'emitted_at',
                'category',
                'severity',
                'event_type',
                'subject_type',
                'subject_id',
                'trace_id',
            ),
            'filters': {
                'category': str(normalized.get('category') or '').strip(),
                'severity': str(normalized.get('severity') or '').strip(),
                'event_type_prefix': str(normalized.get('event_type_prefix') or '').strip(),
            },
            'summary': {
                'security_count': sum(1 for row in rows if str(row.get('category') or '') == 'security'),
                'critical_count': sum(1 for row in rows if str(row.get('severity') or '') == 'critical'),
            },
            'tenant_bound': True,
            'redacted': True,
        }
        return build_kinded_payload(self.kind, result)

    def build_from_events(
        self,
        *,
        tenant_id: str,
        events: Iterable[Any],
        category: str | None = None,
        severity: str | None = None,
        event_type_prefix: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        normalized_category = str(category or '').strip()
        normalized_severity = str(severity or '').strip()
        normalized_prefix = str(event_type_prefix or '').strip()
        normalized_limit = _safe_int(limit, default=100, minimum=1, maximum=_MAX_LIMIT)
        rows: list[dict[str, Any]] = []
        for event in events:
            event_tenant_id = normalize_tenant_id(getattr(event, 'tenant_id', ''))
            if event_tenant_id and event_tenant_id != required_tenant_id:
                continue
            row = _row_from_event(event, self.audit_redaction_policy)
            row['tenant_id'] = required_tenant_id
            if normalized_category and str(row.get('category') or '') != normalized_category:
                continue
            if normalized_severity and str(row.get('severity') or '') != normalized_severity:
                continue
            if normalized_prefix and not str(row.get('event_type') or '').startswith(normalized_prefix):
                continue
            rows.append(row)
            if len(rows) >= normalized_limit:
                break
        return self.build(
            {
                'tenant_id': required_tenant_id,
                'rows': tuple(rows),
                'category': normalized_category,
                'severity': normalized_severity,
                'event_type_prefix': normalized_prefix,
            }
        )


__all__ = ['AuditLogTable', 'CANON_WEB_AUDIT_LOG_TABLE']
