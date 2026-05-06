from __future__ import annotations

"""Operator recovery panel.

Evidence-only renderer for canonical recovery surfaces.
It does not perform recovery and does not decide policy.
"""

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from core.tenancy.normalization import require_tenant_id
from security.payload_redaction import PayloadRedactor
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_RECOVERY_PANEL = True
_MAX_TRANSPORT_ROWS = 500


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


def _tuple_text(value: Any) -> tuple[str, ...]:
    return tuple(sorted({_text(item) for item in tuple(value or ()) if _text(item)}))


def _transport_row(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return {
            'transport_name': _text(item.get('transport_name')) or 'unknown',
            'worker_id': _text(item.get('worker_id')) or None,
            'backend_name': _text(item.get('backend_name')) or None,
            'processed': _safe_int(item.get('processed'), default=0, minimum=0),
            'delivered': _safe_int(item.get('delivered'), default=0, minimum=0),
            'retried': _safe_int(item.get('retried'), default=0, minimum=0),
            'dead_lettered': _safe_int(item.get('dead_lettered'), default=0, minimum=0),
            'skipped': _safe_int(item.get('skipped'), default=0, minimum=0),
        }
    return {
        'transport_name': _text(getattr(item, 'transport_name', '')) or 'unknown',
        'worker_id': _text(getattr(item, 'worker_id', '')) or None,
        'backend_name': _text(getattr(item, 'backend_name', '')) or None,
        'processed': _safe_int(getattr(item, 'processed', 0), default=0, minimum=0),
        'delivered': _safe_int(getattr(item, 'delivered', 0), default=0, minimum=0),
        'retried': _safe_int(getattr(item, 'retried', 0), default=0, minimum=0),
        'dead_lettered': _safe_int(getattr(item, 'dead_lettered', 0), default=0, minimum=0),
        'skipped': _safe_int(getattr(item, 'skipped', 0), default=0, minimum=0),
    }


@dataclass(frozen=True, slots=True)
class RecoveryPanel:
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    kind: str = 'recovery_panel'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))

        plan_in = _mapping_copy(normalized.get('plan'))
        reconciliation_in = _mapping_copy(normalized.get('reconciliation'))
        plan = {
            'run_id': _text(plan_in.get('run_id')) or None,
            'recovery_action': _text(plan_in.get('recovery_action')) or None,
            'reason': _text(plan_in.get('reason')) or None,
            'delivery_hint': _text(plan_in.get('delivery_hint')) or None,
            'dead_letter_hint': _text(plan_in.get('dead_letter_hint')) or None,
            'operator_required': _safe_bool(plan_in.get('operator_required', False)),
            'operator_hint': _text(plan_in.get('operator_hint')) or None,
            'resume_action': _text(plan_in.get('resume_action')) or None,
            'resume_stage': _text(plan_in.get('resume_stage')) or None,
            'anomalies': _tuple_text(plan_in.get('anomalies')),
            'risk_flags': _tuple_text(plan_in.get('risk_flags')),
            'policy_snapshot': _mapping_copy(plan_in.get('policy_snapshot')),
        }
        reconciliation = {
            'ok': _safe_bool(reconciliation_in.get('ok', reconciliation_in.get('is_clean', False))),
            'checkpoint_present': _safe_bool(reconciliation_in.get('checkpoint_present', _safe_int(reconciliation_in.get('checkpoint_count'), default=0, minimum=0) > 0)),
            'idempotency_present': bool(_text(reconciliation_in.get('idempotency_state'))),
            'outbox_present': bool(_text(reconciliation_in.get('outbox_state'))),
            'outbox_state': _text(reconciliation_in.get('outbox_state')) or None,
            'latest_stage': _text(reconciliation_in.get('latest_stage')) or None,
            'checkpoint_count': _safe_int(reconciliation_in.get('checkpoint_count'), default=0, minimum=0),
            'idempotency_state': _text(reconciliation_in.get('idempotency_state')) or None,
            'anomalies': _tuple_text(reconciliation_in.get('anomalies')),
            'metadata': _mapping_copy(reconciliation_in.get('metadata')),
        }
        transport_rows: list[dict[str, Any]] = []
        for item in tuple(normalized.get('transport_results', ()) or ()):
            transport_rows.append(_transport_row(item))
            if len(transport_rows) >= _MAX_TRANSPORT_ROWS:
                break
        transport_rows.sort(key=lambda row: (-_safe_int(row.get('dead_lettered'), default=0, minimum=0), -_safe_int(row.get('retried'), default=0, minimum=0), str(row.get('transport_name') or '')))

        total_processed = sum(_safe_int(row.get('processed'), default=0, minimum=0) for row in transport_rows)
        total_delivered = sum(_safe_int(row.get('delivered'), default=0, minimum=0) for row in transport_rows)
        total_retried = sum(_safe_int(row.get('retried'), default=0, minimum=0) for row in transport_rows)
        total_dead_lettered = sum(_safe_int(row.get('dead_lettered'), default=0, minimum=0) for row in transport_rows)
        total_skipped = sum(_safe_int(row.get('skipped'), default=0, minimum=0) for row in transport_rows)

        result = {
            'tenant_id': tenant_id,
            'title': 'Recovery',
            'plan': plan,
            'reconciliation': reconciliation,
            'transport_results': tuple(transport_rows),
            'summary': {
                'requires_operator_attention': bool(plan['operator_required'] or plan['anomalies'] or plan['risk_flags'] or reconciliation['anomalies'] or total_dead_lettered > 0),
                'has_resume_path': bool(plan['resume_action'] or plan['resume_stage']),
                'transport_worker_count': len(transport_rows),
                'processed': total_processed,
                'delivered': total_delivered,
                'retried': total_retried,
                'dead_lettered': total_dead_lettered,
                'skipped': total_skipped,
            },
            'tenant_bound': True,
            'read_only': True,
        }
        return build_kinded_payload(self.kind, self.payload_redactor.redact(result))

    def build_from_plan(self, *, tenant_id: str, plan: Any, transport_results: Iterable[Any] = ()) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        reconciliation_obj = getattr(plan, 'reconciliation', None)
        reconciliation = {}
        if reconciliation_obj is not None:
            reconciliation = {
                'ok': bool(getattr(reconciliation_obj, 'is_clean', False)),
                'checkpoint_present': int(getattr(reconciliation_obj, 'checkpoint_count', 0) or 0) > 0,
                'idempotency_present': bool(getattr(reconciliation_obj, 'idempotency_state', None)),
                'outbox_present': bool(getattr(reconciliation_obj, 'outbox_state', None)),
                'outbox_state': _text(getattr(reconciliation_obj, 'outbox_state', '')) or None,
                'latest_stage': _text(getattr(reconciliation_obj, 'latest_stage', '')) or None,
                'checkpoint_count': int(getattr(reconciliation_obj, 'checkpoint_count', 0) or 0),
                'idempotency_state': _text(getattr(reconciliation_obj, 'idempotency_state', '')) or None,
                'anomalies': tuple(getattr(reconciliation_obj, 'anomalies', ()) or ()),
                'metadata': _mapping_copy(getattr(reconciliation_obj, 'metadata', {})),
            }
        return self.build({'tenant_id': required_tenant_id, 'plan': {'run_id': _text(getattr(plan, 'run_id', '')) or None, 'recovery_action': _text(getattr(plan, 'recovery_action', '')) or None, 'reason': _text(getattr(plan, 'reason', '')) or None, 'delivery_hint': _text(getattr(plan, 'delivery_hint', '')) or None, 'dead_letter_hint': _text(getattr(plan, 'dead_letter_hint', '')) or None, 'operator_required': bool(getattr(plan, 'operator_required', False)), 'operator_hint': _text(getattr(plan, 'operator_hint', '')) or None, 'resume_action': _text(getattr(plan, 'resume_action', '')) or None, 'resume_stage': _text(getattr(plan, 'resume_stage', '')) or None, 'anomalies': tuple(getattr(plan, 'anomalies', ()) or ()), 'risk_flags': tuple(getattr(plan, 'risk_flags', ()) or ()), 'policy_snapshot': _mapping_copy(getattr(plan, 'policy_snapshot', {}))}, 'reconciliation': reconciliation, 'transport_results': tuple(transport_results or ())})


__all__ = ['CANON_WEB_RECOVERY_PANEL', 'RecoveryPanel']
