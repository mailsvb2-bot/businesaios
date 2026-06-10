from __future__ import annotations

"""Redacted runtime alerts card."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping

from core.tenancy.normalization import normalize_tenant_id, require_tenant_id
from security.payload_redaction import PayloadRedactor
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_RUNTIME_ALERTS_CARD = True
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


def _alert_row(item: Any) -> dict[str, Any]:
    return {
        'incident_id': str(getattr(item, 'incident_id', '') or '').strip(),
        'tenant_id': str(getattr(item, 'tenant_id', '') or '').strip(),
        'signal_type': str(getattr(item, 'signal_type', '') or '').strip(),
        'status': _enum_value(getattr(item, 'status', '')),
        'severity': str(getattr(item, 'severity', 'warning') or 'warning').strip(),
        'trace_id': getattr(item, 'trace_id', None),
        'rule_id': getattr(item, 'rule_id', None),
        'summary': str(getattr(item, 'summary', '') or '').strip(),
        'created_at': _iso(getattr(item, 'created_at', None)),
        'updated_at': _iso(getattr(item, 'updated_at', None)),
        'payload': dict(getattr(item, 'payload', {}) or {}),
    }


@dataclass(frozen=True, slots=True)
class RuntimeAlertsCard:
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    kind: str = 'runtime_alerts_card'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        rows: list[dict[str, Any]] = []
        for item in tuple(normalized.get('alerts', ()) or ()):
            row = dict(item or {})
            row_tenant_id = normalize_tenant_id(row.get('tenant_id'))
            if row_tenant_id and row_tenant_id != tenant_id:
                continue
            row['tenant_id'] = tenant_id
            rows.append(row)
        rows.sort(key=lambda item: (str(item.get('severity') or ''), str(item.get('updated_at') or ''), str(item.get('incident_id') or '')), reverse=True)
        result = {
            'tenant_id': tenant_id,
            'alert_count': len(rows),
            'alerts': tuple(rows),
            'has_critical': any(str(item.get('severity') or '') == 'critical' for item in rows),
            'has_open': any(str(item.get('status') or '') == 'open' for item in rows),
            'summary': {
                'open_count': sum(1 for item in rows if str(item.get('status') or '') == 'open'),
                'acknowledged_count': sum(1 for item in rows if str(item.get('status') or '') == 'acknowledged'),
                'critical_count': sum(1 for item in rows if str(item.get('severity') or '') == 'critical'),
            },
            'tenant_bound': True,
        }
        return build_kinded_payload(self.kind, self.payload_redactor.redact(result))

    def build_from_incidents(self, *, tenant_id: str, alerts: Iterable[Any], limit: int = 20) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        normalized_limit = _safe_int(limit, default=20, minimum=1, maximum=_MAX_LIMIT)
        rows: list[dict[str, Any]] = []
        for item in alerts:
            row = _alert_row(item)
            row_tenant_id = normalize_tenant_id(row.get('tenant_id'))
            if row_tenant_id and row_tenant_id != required_tenant_id:
                continue
            row['tenant_id'] = required_tenant_id
            rows.append(row)
            if len(rows) >= normalized_limit:
                break
        return self.build({'tenant_id': required_tenant_id, 'alerts': tuple(rows)})


__all__ = ['RuntimeAlertsCard', 'CANON_WEB_RUNTIME_ALERTS_CARD']
