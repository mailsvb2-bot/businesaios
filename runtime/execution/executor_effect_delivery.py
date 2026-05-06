from __future__ import annotations

from typing import Any, Mapping

from runtime.execution.executor_commit import _decision_tenant_id, get_delivery_info


def safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def attach_effect_delivery_metadata(self, *, env, output: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = safe_dict(output)
    decision = getattr(env, 'decision', None)
    decision_id = str(getattr(decision, 'decision_id', '') or '')
    correlation_id = str(getattr(decision, 'correlation_id', '') or '')
    delivery = {
        'decision_id': decision_id,
        'correlation_id': correlation_id,
        'guarantee': 'executor_outbox_claim_and_reconcile',
    }
    outbox = getattr(self, '_outbox', None)
    if outbox is not None:
        try:
            row = get_delivery_info(
                outbox,
                decision_id=decision_id,
                tenant_id=_decision_tenant_id(decision),
            )
        except Exception:
            row = None
        if isinstance(row, Mapping):
            delivery['runtime_outbox_status'] = row.get('status') or row.get('state')
            delivery['runtime_outbox_retry_count'] = row.get('retry_count') or row.get('delivery_attempts')
            delivery['runtime_outbox_backend_name'] = row.get('backend_name')
            delivery['runtime_outbox_external_id'] = row.get('external_id')
            delivery['runtime_outbox_effect_key'] = row.get('effect_key')
            delivery['runtime_outbox_effect_kind'] = row.get('effect_kind')
            delivery['runtime_outbox_payload_digest'] = row.get('payload_digest')
            delivery['runtime_outbox_delivered_at'] = row.get('delivered_at')
            delivery['runtime_outbox_delivery_metadata'] = safe_dict(row.get('delivery_metadata'))
    handler_meta = safe_dict(payload.get('meta'))
    if handler_meta:
        delivery['transport_meta'] = handler_meta
    reliability = getattr(self, '_reliability', None)
    if reliability is not None and hasattr(reliability, 'reconcile'):
        try:
            delivery['reconciliation'] = reliability.reconcile(env)
        except Exception:
            delivery['reconciliation'] = None
    return {**payload, 'effect_delivery': delivery}
