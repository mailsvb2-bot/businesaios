from __future__ import annotations

"""Operator autonomy budget panel.

Read-only visualization for tenant execution budget, quota, and runtime guard results.
No policy decisions are made here.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from security.payload_redaction import PayloadRedactor
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_AUTONOMY_BUDGET_PANEL = True


def _safe_int(value: Any, *, default: int = 0, minimum: int | None = None) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    if minimum is not None:
        result = max(minimum, result)
    return result


def _safe_float(value: Any, *, default: float = 0.0, minimum: float | None = None) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = default
    if minimum is not None:
        result = max(minimum, result)
    return result


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def _text(value: Any) -> str:
    return str(value or '').strip()


def _mapping_copy(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(k): v for k, v in value.items()}


def _runtime_check_row(name: str, item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return {'name': str(name), 'allowed': _safe_bool(item.get('allowed', False)), 'requested': _safe_float(item.get('requested'), default=0.0, minimum=0.0), 'limit': _safe_float(item.get('limit'), default=0.0, minimum=0.0)}
    return {'name': str(name), 'allowed': _safe_bool(getattr(item, 'allowed', False)), 'requested': _safe_float(getattr(item, 'requested', 0.0), default=0.0, minimum=0.0), 'limit': _safe_float(getattr(item, 'limit', 0.0), default=0.0, minimum=0.0)}


def _quota_check_row(name: str, item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return {
            'dimension': _text(item.get('dimension')) or str(name),
            'allowed': _safe_bool(item.get('allowed', False)),
            'reason': _text(item.get('reason')) or None,
            'requested': _safe_float(item.get('requested'), default=0.0, minimum=0.0),
            'used': _safe_float(item.get('used'), default=0.0, minimum=0.0),
            'limit': None if item.get('limit') is None else _safe_float(item.get('limit'), default=0.0, minimum=0.0),
            'remaining': None if item.get('remaining') is None else _safe_float(item.get('remaining'), default=0.0),
            'retry_after_seconds': None if item.get('retry_after_seconds') is None else _safe_int(item.get('retry_after_seconds'), default=0, minimum=0),
        }
    return {
        'dimension': _text(getattr(item, 'dimension', '')) or str(name),
        'allowed': _safe_bool(getattr(item, 'allowed', False)),
        'reason': _text(getattr(item, 'reason', '')) or None,
        'requested': _safe_float(getattr(item, 'requested', 0.0), default=0.0, minimum=0.0),
        'used': _safe_float(getattr(item, 'used', 0.0), default=0.0, minimum=0.0),
        'limit': None if getattr(item, 'limit', None) is None else _safe_float(getattr(item, 'limit', 0.0), default=0.0, minimum=0.0),
        'remaining': None if getattr(item, 'remaining', None) is None else _safe_float(getattr(item, 'remaining', 0.0), default=0.0),
        'retry_after_seconds': None if getattr(item, 'retry_after_seconds', None) is None else _safe_int(getattr(item, 'retry_after_seconds', 0), default=0, minimum=0),
    }


@dataclass(frozen=True, slots=True)
class AutonomyBudgetPanel:
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    kind: str = 'autonomy_budget_panel'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))

        usage_in = _mapping_copy(normalized.get('usage'))
        verdict_in = _mapping_copy(normalized.get('verdict'))
        usage = {
            'action_count': _safe_int(usage_in.get('action_count'), default=0, minimum=0),
            'effect_count': _safe_int(usage_in.get('effect_count'), default=0, minimum=0),
            'outbound_message_count': _safe_int(usage_in.get('outbound_message_count'), default=0, minimum=0),
            'publication_count': _safe_int(usage_in.get('publication_count'), default=0, minimum=0),
            'memory_write_count': _safe_int(usage_in.get('memory_write_count'), default=0, minimum=0),
            'connector_call_count': _safe_int(usage_in.get('connector_call_count'), default=0, minimum=0),
            'budget_delta': round(_safe_float(usage_in.get('budget_delta'), default=0.0, minimum=0.0), 6),
            'labels': _mapping_copy(usage_in.get('labels')),
        }
        verdict = {
            'allowed': _safe_bool(verdict_in.get('allowed', False)),
            'reason': _text(verdict_in.get('reason')) or 'unknown',
            'consumed': _safe_bool(verdict_in.get('consumed', False)),
            'violations': tuple(sorted({_text(item) for item in tuple(verdict_in.get('violations', ()) or ()) if _text(item)})),
        }
        runtime_rows = [_runtime_check_row(name, item) for name, item in _mapping_copy(normalized.get('runtime_limit_checks')).items()]
        quota_rows = [_quota_check_row(name, item) for name, item in _mapping_copy(normalized.get('quota_checks')).items()]
        runtime_rows.sort(key=lambda row: (bool(row['allowed']), str(row['name'])))
        quota_rows.sort(key=lambda row: (bool(row['allowed']), str(row['dimension'])))
        runtime_violation_count = sum(1 for row in runtime_rows if not bool(row['allowed']))
        quota_violation_count = sum(1 for row in quota_rows if not bool(row['allowed']))
        result = {
            'tenant_id': tenant_id,
            'title': 'Autonomy Budget',
            'usage': usage,
            'verdict': verdict,
            'runtime_limit_checks': tuple(runtime_rows),
            'quota_checks': tuple(quota_rows),
            'summary': {
                'runtime_violation_count': runtime_violation_count,
                'quota_violation_count': quota_violation_count,
                'total_violation_count': runtime_violation_count + quota_violation_count,
                'budget_delta': usage['budget_delta'],
                'operator_attention_required': ((not verdict['allowed']) or bool(verdict['violations']) or runtime_violation_count > 0 or quota_violation_count > 0),
                'noop_usage': (usage['action_count'] == 0 and usage['effect_count'] == 0 and usage['outbound_message_count'] == 0 and usage['publication_count'] == 0 and usage['memory_write_count'] == 0 and usage['connector_call_count'] == 0 and float(usage['budget_delta']) == 0.0),
            },
            'tenant_bound': True,
            'read_only': True,
        }
        return build_kinded_payload(self.kind, self.payload_redactor.redact(result))

    def build_from_verdict(self, *, tenant_id: str, usage: Any, verdict: Any) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        runtime_limit_checks = {str(name): item for name, item in dict(getattr(verdict, 'runtime_limit_checks', {}) or {}).items()}
        quota_checks = {str(name): item for name, item in dict(getattr(verdict, 'quota_checks', {}) or {}).items()}
        return self.build({'tenant_id': required_tenant_id, 'usage': {'action_count': getattr(usage, 'action_count', 0), 'effect_count': getattr(usage, 'effect_count', 0), 'outbound_message_count': getattr(usage, 'outbound_message_count', 0), 'publication_count': getattr(usage, 'publication_count', 0), 'memory_write_count': getattr(usage, 'memory_write_count', 0), 'connector_call_count': getattr(usage, 'connector_call_count', 0), 'budget_delta': getattr(usage, 'budget_delta', 0.0), 'labels': dict(getattr(usage, 'labels', {}) or {})}, 'verdict': {'allowed': bool(getattr(verdict, 'allowed', False)), 'reason': _text(getattr(verdict, 'reason', '')) or 'unknown', 'consumed': bool(getattr(verdict, 'consumed', False)), 'violations': tuple(getattr(verdict, 'violations', ()) or ())}, 'runtime_limit_checks': runtime_limit_checks, 'quota_checks': quota_checks})


__all__ = ['CANON_WEB_AUTONOMY_BUDGET_PANEL', 'AutonomyBudgetPanel']
