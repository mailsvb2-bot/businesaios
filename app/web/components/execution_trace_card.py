from __future__ import annotations

"""Execution trace card for operator console.

Evidence-only renderer over canonical trace events.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping

from core.tenancy.normalization import normalize_tenant_id, require_tenant_id
from security.payload_redaction import PayloadRedactor
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_EXECUTION_TRACE_CARD = True
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


def _trace_row(item: Any) -> dict[str, Any]:
    return {
        'tenant_id': str(getattr(item, 'tenant_id', '') or '').strip(),
        'trace_id': str(getattr(item, 'trace_id', '') or '').strip(),
        'run_id': str(getattr(item, 'run_id', '') or '').strip(),
        'sequence_no': _safe_int(getattr(item, 'sequence_no', 0), default=0, minimum=0),
        'stage': _enum_value(getattr(item, 'stage', '')),
        'event_type': str(getattr(item, 'event_type', '') or '').strip(),
        'emitted_at': _iso(getattr(item, 'emitted_at', None)),
        'correlation_id': getattr(item, 'correlation_id', None),
        'decision_id': getattr(item, 'decision_id', None),
        'action_id': getattr(item, 'action_id', None),
        'executor_name': getattr(item, 'executor_name', None),
        'component': getattr(item, 'component', None),
        'payload': dict(getattr(item, 'payload', {}) or {}),
    }


@dataclass(frozen=True, slots=True)
class ExecutionTraceCard:
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    kind: str = 'execution_trace_card'

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
        rows.sort(key=lambda row: (_safe_int(row.get('sequence_no'), default=0, minimum=0), str(row.get('emitted_at') or ''), str(row.get('event_type') or '')))
        trace_id = str(normalized.get('trace_id') or rows[0].get('trace_id') if rows else '').strip()
        run_id = str(normalized.get('run_id') or rows[0].get('run_id') if rows else '').strip()
        result = {
            'tenant_id': tenant_id,
            'trace_id': trace_id,
            'run_id': run_id,
            'event_count': len(rows),
            'events': tuple(rows),
            'completed': any(str(item.get('stage') or '') == 'completed' for item in rows),
            'failed': any(str(item.get('stage') or '') == 'failed' for item in rows),
            'summary': {
                'verification_count': sum(1 for item in rows if str(item.get('stage') or '') == 'verification'),
                'execution_count': sum(1 for item in rows if str(item.get('stage') or '') == 'execution'),
                'evidence_count': sum(1 for item in rows if str(item.get('stage') or '') == 'evidence'),
            },
            'tenant_bound': True,
        }
        return build_kinded_payload(self.kind, self.payload_redactor.redact(result))

    def build_from_events(
        self,
        *,
        tenant_id: str,
        events: Iterable[Any],
        trace_id: str | None = None,
        run_id: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        normalized_trace_id = str(trace_id or '').strip()
        normalized_run_id = str(run_id or '').strip()
        normalized_limit = _safe_int(limit, default=100, minimum=1, maximum=_MAX_LIMIT)
        rows: list[dict[str, Any]] = []
        for item in events:
            row = _trace_row(item)
            row_tenant_id = normalize_tenant_id(row.get('tenant_id'))
            if row_tenant_id and row_tenant_id != required_tenant_id:
                continue
            if normalized_trace_id and str(row.get('trace_id') or '') != normalized_trace_id:
                continue
            if normalized_run_id and str(row.get('run_id') or '') != normalized_run_id:
                continue
            row['tenant_id'] = required_tenant_id
            rows.append(row)
            if len(rows) >= normalized_limit:
                break
        return self.build({'tenant_id': required_tenant_id, 'trace_id': normalized_trace_id, 'run_id': normalized_run_id, 'events': tuple(rows)})


__all__ = ['ExecutionTraceCard', 'CANON_WEB_EXECUTION_TRACE_CARD']
