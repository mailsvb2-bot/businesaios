from __future__ import annotations

"""Operator dead-letter panel.

Read-only renderer over canonical dead-letter/outbox-failure facts.
No replay logic or recovery decisions live here.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping

from core.tenancy.normalization import normalize_tenant_id, require_tenant_id
from reliability.outbox_store import OutboxState
from security.payload_redaction import PayloadRedactor
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_DEAD_LETTER_PANEL = True
_MAX_ROWS = 1000


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


def _text(value: Any) -> str:
    return str(value or '').strip()


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    text = _text(value)
    return text or None


def _mapping_copy(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(k): v for k, v in value.items()}


def _state_text(value: Any) -> str:
    if isinstance(value, OutboxState):
        return value.value
    return _text(getattr(value, 'value', value))


def _row_from_mapping(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'tenant_id': _text(item.get('tenant_id')),
        'entry_kind': _text(item.get('entry_kind')) or 'outbox',
        'message_id': _text(item.get('message_id')) or None,
        'run_id': _text(item.get('run_id')) or None,
        'trace_id': _text(item.get('trace_id')) or None,
        'decision_id': _text(item.get('decision_id')) or None,
        'topic': _text(item.get('topic')) or None,
        'dedupe_key': _text(item.get('dedupe_key')) or None,
        'state': _state_text(item.get('state')) or 'dead',
        'delivery_attempts': _safe_int(item.get('delivery_attempts'), default=0, minimum=0),
        'last_error': _text(item.get('last_error')) or None,
        'backend_name': _text(item.get('backend_name')) or None,
        'external_id': _text(item.get('external_id')) or None,
        'created_at': _iso(item.get('created_at')),
        'updated_at': _iso(item.get('updated_at')),
        'available_at': _iso(item.get('available_at')),
        'delivered_at': _iso(item.get('delivered_at')),
        'payload': _mapping_copy(item.get('payload')),
        'metadata': _mapping_copy(item.get('metadata')),
        'delivery_metadata': _mapping_copy(item.get('delivery_metadata')),
    }


def _row_from_object(item: Any) -> dict[str, Any]:
    return {
        'tenant_id': _text(getattr(item, 'tenant_id', '')),
        'entry_kind': 'outbox',
        'message_id': _text(getattr(item, 'message_id', '')) or None,
        'run_id': _text(getattr(item, 'run_id', '')) or None,
        'trace_id': _text(getattr(item, 'trace_id', '')) or None,
        'decision_id': _text(getattr(item, 'decision_id', '')) or None,
        'topic': _text(getattr(item, 'topic', '')) or None,
        'dedupe_key': _text(getattr(item, 'dedupe_key', '')) or None,
        'state': _state_text(getattr(item, 'state', '')) or 'dead',
        'delivery_attempts': _safe_int(getattr(item, 'delivery_attempts', 0), default=0, minimum=0),
        'last_error': _text(getattr(item, 'last_error', '')) or None,
        'backend_name': _text(getattr(item, 'backend_name', '')) or None,
        'external_id': _text(getattr(item, 'external_id', '')) or None,
        'created_at': _iso(getattr(item, 'created_at', None)),
        'updated_at': _iso(getattr(item, 'updated_at', None)),
        'available_at': _iso(getattr(item, 'available_at', None)),
        'delivered_at': _iso(getattr(item, 'delivered_at', None)),
        'payload': _mapping_copy(getattr(item, 'payload', {})),
        'metadata': {},
        'delivery_metadata': _mapping_copy(getattr(item, 'delivery_metadata', {})),
    }


@dataclass(frozen=True, slots=True)
class DeadLetterPanel:
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    kind: str = 'dead_letter_panel'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))

        rows: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for item in tuple(normalized.get('rows', ()) or ()):
            row = _row_from_mapping(item) if isinstance(item, Mapping) else _row_from_object(item)
            row_tenant_id = normalize_tenant_id(row.get('tenant_id'))
            if row_tenant_id and row_tenant_id != tenant_id:
                continue
            row['tenant_id'] = tenant_id
            stable_id = str(row.get('message_id') or row.get('dedupe_key') or '')
            if stable_id and stable_id in seen_ids:
                continue
            if stable_id:
                seen_ids.add(stable_id)
            rows.append(row)
            if len(rows) >= _MAX_ROWS:
                break
        rows.sort(key=lambda row: (str(row.get('updated_at') or ''), str(row.get('created_at') or ''), str(row.get('message_id') or '')), reverse=True)

        reason_breakdown: dict[str, int] = {}
        topic_breakdown: dict[str, int] = {}
        backend_breakdown: dict[str, int] = {}
        for row in rows:
            reason = str(row.get('last_error') or 'unknown')
            topic = str(row.get('topic') or 'unknown')
            backend = str(row.get('backend_name') or 'unknown')
            reason_breakdown[reason] = reason_breakdown.get(reason, 0) + 1
            topic_breakdown[topic] = topic_breakdown.get(topic, 0) + 1
            backend_breakdown[backend] = backend_breakdown.get(backend, 0) + 1

        result = {
            'tenant_id': tenant_id,
            'title': 'Dead Letter',
            'rows': tuple(rows),
            'summary': {
                'row_count': len(rows),
                'with_run_id_count': sum(1 for row in rows if bool(row.get('run_id'))),
                'with_trace_id_count': sum(1 for row in rows if bool(row.get('trace_id'))),
                'with_decision_id_count': sum(1 for row in rows if bool(row.get('decision_id'))),
                'delivery_attempted_count': sum(1 for row in rows if _safe_int(row.get('delivery_attempts'), default=0, minimum=0) > 0),
                'dead_state_count': sum(1 for row in rows if str(row.get('state') or '') == OutboxState.DEAD.value),
            },
            'reason_breakdown': tuple({'reason': key, 'count': value} for key, value in sorted(reason_breakdown.items(), key=lambda item: (-item[1], item[0]))),
            'topic_breakdown': tuple({'topic': key, 'count': value} for key, value in sorted(topic_breakdown.items(), key=lambda item: (-item[1], item[0]))),
            'backend_breakdown': tuple({'backend_name': key, 'count': value} for key, value in sorted(backend_breakdown.items(), key=lambda item: (-item[1], item[0]))),
            'tenant_bound': True,
            'read_only': True,
        }
        return build_kinded_payload(self.kind, self.payload_redactor.redact(result))

    def build_from_entries(self, *, tenant_id: str, entries: Iterable[Any], limit: int = 200) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        bounded_limit = _safe_int(limit, default=200, minimum=1, maximum=_MAX_ROWS)
        rows: list[Any] = []
        for item in entries:
            item_tenant_id = normalize_tenant_id(item.get('tenant_id') if isinstance(item, Mapping) else getattr(item, 'tenant_id', None))
            if item_tenant_id and item_tenant_id != required_tenant_id:
                continue
            rows.append(item)
            if len(rows) >= bounded_limit:
                break
        return self.build({'tenant_id': required_tenant_id, 'rows': tuple(rows)})


__all__ = ['CANON_WEB_DEAD_LETTER_PANEL', 'DeadLetterPanel']
