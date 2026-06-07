"""Canonical event-store call discipline.

Prevents false fallback behavior where an internal ``TypeError`` from the store
implementation could be mistaken for a signature mismatch.
"""

from __future__ import annotations

from typing import Any
from collections.abc import Callable

from core.utils.call_signature import accepts_keyword as _accepts_keyword

CANON_EVENT_STORE_CALL_DISCIPLINE = True

def call_append_event(*, append_fn: Callable[..., Any], event_dict: dict[str, Any], commit: bool) -> Any:
    if _accepts_keyword(append_fn, 'commit'):
        return append_fn(event_dict, commit=bool(commit))
    return append_fn(event_dict)


__all__ = ['CANON_EVENT_STORE_CALL_DISCIPLINE', 'call_append_event']
