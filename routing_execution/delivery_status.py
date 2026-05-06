from __future__ import annotations

from shared.numbers import coerce_int

ALLOWED_DELIVERY_STATUSES = frozenset({'ok', 'accepted', 'queued', 'delivered', 'duplicate'})
DELIVERED_EQUIVALENTS = frozenset({'ok', 'delivered'})
NON_TERMINAL_DELIVERY_STATUSES = frozenset({'accepted', 'queued'})
PERSISTED_DELIVERY_STATUSES = frozenset({'accepted', 'queued', 'delivered', 'duplicate'})


def normalize_delivery_status(raw_status: object) -> str:
    status = str(raw_status or '').strip().lower()
    if status not in ALLOWED_DELIVERY_STATUSES:
        raise ValueError(f'invalid delivery status: {status or "<empty>"}')
    return 'delivered' if status in DELIVERED_EQUIVALENTS else status


def delivered_at_ms_for_status(status: object, *, now_ms: int | None = None) -> int | None:
    normalized = normalize_delivery_status(status)
    if normalized != 'delivered':
        return None
    return coerce_int(now_ms, 0, minimum=1) if now_ms is not None else None


def persisted_delivery_status(status: object, *, delivery_missing: bool = False) -> str:
    if delivery_missing:
        return 'manual_review'
    normalized = normalize_delivery_status(status)
    return normalized if normalized in PERSISTED_DELIVERY_STATUSES else 'unknown'
