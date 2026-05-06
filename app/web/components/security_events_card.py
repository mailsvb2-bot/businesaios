from __future__ import annotations

"""Security-focused redacted event card."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping

from core.tenancy.normalization import normalize_tenant_id, require_tenant_id
from security.audit_redaction_policy import AuditRedactionPolicy
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_SECURITY_EVENTS_CARD = True
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


def _event_row(event: Any, policy: AuditRedactionPolicy) -> dict[str, Any]:
    raw = {
        'audit_id': getattr(event, 'audit_id', getattr(event, 'event_id', '')),
        'tenant_id': getattr(event, 'tenant_id', ''),
        'event_type': getattr(event, 'event_type', ''),
        'category': _enum_value(getattr(event, 'category', '')),
        'severity': _enum_value(getattr(event, 'severity', '')),
        'emitted_at': _iso(getattr(event, 'emitted_at', None)),
        'actor_id': getattr(event, 'actor_id', None),
        'subject_type': getattr(event, 'subject_type', None),
        'subject_id': getattr(event, 'subject_id', None),
        'source_component': getattr(event, 'source_component', None),
        'trace_id': getattr(event, 'trace_id', None),
        'tags': tuple(str(x) for x in tuple(getattr(event, 'tags', ()) or ())),
        'payload': dict(getattr(event, 'payload', {}) or {}),
        'metadata': dict(getattr(event, 'metadata', {}) or {}),
    }
    return policy.redact_event_dict(raw)


@dataclass(frozen=True, slots=True)
class SecurityEventsCard:
    audit_redaction_policy: AuditRedactionPolicy = field(default_factory=AuditRedactionPolicy)
    kind: str = 'security_events_card'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        rows: list[dict[str, Any]] = []
        for item in tuple(normalized.get('events', ()) or ()):
            row = dict(item or {})
            row_tenant_id = normalize_tenant_id(row.get('tenant_id'))
            if row_tenant_id and row_tenant_id != tenant_id:
                continue
            row['tenant_id'] = tenant_id
            rows.append(row)
        rows.sort(key=lambda item: (str(item.get('severity') or ''), str(item.get('emitted_at') or ''), str(item.get('audit_id') or '')), reverse=True)
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'event_count': len(rows),
                'events': tuple(rows),
                'critical_count': sum(1 for item in rows if str(item.get('severity') or '') == 'critical'),
                'auth_related_count': sum(1 for item in rows if 'auth' in str(item.get('event_type') or '')),
                'redacted': True,
                'tenant_bound': True,
            },
        )

    def build_from_events(self, *, tenant_id: str, events: Iterable[Any], limit: int = 50) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        normalized_limit = _safe_int(limit, default=50, minimum=1, maximum=_MAX_LIMIT)
        rows: list[dict[str, Any]] = []
        for item in events:
            row = _event_row(item, self.audit_redaction_policy)
            row_tenant_id = normalize_tenant_id(row.get('tenant_id'))
            if row_tenant_id and row_tenant_id != required_tenant_id:
                continue
            category = str(row.get('category') or '')
            if category and category != 'security':
                continue
            row['tenant_id'] = required_tenant_id
            rows.append(row)
            if len(rows) >= normalized_limit:
                break
        return self.build({'tenant_id': required_tenant_id, 'events': tuple(rows)})


__all__ = ['SecurityEventsCard', 'CANON_WEB_SECURITY_EVENTS_CARD']
