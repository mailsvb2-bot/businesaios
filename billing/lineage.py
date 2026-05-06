from __future__ import annotations

from typing import Mapping


CANON_BILLING_LINEAGE = True


def invoice_lineage_root(invoice_id: str) -> str:
    normalized = str(invoice_id or '').strip()
    if not normalized:
        raise ValueError('invoice_id is required')
    return f'billing:invoice:{normalized}'


def derive_lineage_metadata(*, invoice_id: str, invoice_metadata: Mapping[str, object] | None = None, event_type: str, event_id: str, idempotency_key: str | None = None, provider_name: str | None = None, extra: Mapping[str, object] | None = None) -> dict[str, object]:
    normalized_event_type = str(event_type or '').strip().lower()
    normalized_event_id = str(event_id or '').strip()
    if not normalized_event_type:
        raise ValueError('event_type is required')
    if not normalized_event_id:
        raise ValueError('event_id is required')
    base = dict(invoice_metadata or {})
    lineage_root = str(base.get('billing_lineage_root') or invoice_lineage_root(invoice_id)).strip()
    if not lineage_root:
        raise ValueError('billing_lineage_root cannot be blank')
    lineage_step = f'{lineage_root}:{normalized_event_type}:{normalized_event_id}'
    result = {
        **base,
        **dict(extra or {}),
        'billing_lineage_root': lineage_root,
        'billing_lineage_step': lineage_step,
        'last_recovery_event_type': normalized_event_type,
        'last_recovery_event_id': normalized_event_id,
    }
    if idempotency_key is not None and str(idempotency_key).strip():
        result['last_recovery_idempotency_key'] = str(idempotency_key).strip()
    if provider_name is not None and str(provider_name).strip():
        result['provider_name_hint'] = str(provider_name).strip()
    return result


__all__ = ['CANON_BILLING_LINEAGE', 'derive_lineage_metadata', 'invoice_lineage_root']
