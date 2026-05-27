"""Thin compatibility shim for delivery state.

The canonical owner lives in :mod:`runtime.platform.delivery_state`.
Keeping only explicit exports here prevents semantic drift and avoids a duplicate
infrastructure owner for accepted/finalized receipt behavior.
"""

from __future__ import annotations

from runtime.platform.delivery_state import (
    ACCEPTED_PHASE,
    DEFAULT_DELIVERY_STATE_POLICY,
    FINALIZED_PHASE,
    DeliveryStatePolicy,
    get_receipt,
    is_accepted,
    is_delivered,
    list_inflight_receipts,
    list_stale_accepted_receipts,
    mark_accepted,
    mark_delivered,
    open_delivery_state,
)

__all__ = [
    "ACCEPTED_PHASE",
    "DEFAULT_DELIVERY_STATE_POLICY",
    "DeliveryStatePolicy",
    "FINALIZED_PHASE",
    "get_receipt",
    "open_delivery_state",
    "is_accepted",
    "is_delivered",
    "list_inflight_receipts",
    "list_stale_accepted_receipts",
    "mark_accepted",
    "mark_delivered",
]
