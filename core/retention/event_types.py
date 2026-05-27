from __future__ import annotations

"""Retention event type compatibility surface.

Single source of truth lives in core.events.event_types.
This module remains as a thin explicit shim for older retention imports.
"""

from core.events.event_types import (
    KNOWN_EVENT_TYPES,
    OFFER_SHOWN,
    PURCHASE_SUCCESS,
    RETENTION_EVENT_TYPES,
    UI_CLICK,
    is_known,
    normalize_event_type,
)

CANON_COMPAT_SHIM = True

__all__ = [
    "KNOWN_EVENT_TYPES",
    "RETENTION_EVENT_TYPES",
    "UI_CLICK",
    "OFFER_SHOWN",
    "PURCHASE_SUCCESS",
    "normalize_event_type",
    "is_known",
]
