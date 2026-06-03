from __future__ import annotations

"""Canonical event-iteration call discipline.

Avoids masking provider bugs as signature mismatches when reading event ranges.
"""

from typing import Any, Callable
from collections.abc import Iterable

from core.utils.call_signature import accepts_keywords as _accepts_keywords

CANON_GROWTH_EVENT_ITER_CALL = True

_FULL_KWARGS = ('tenant_id', 'event_types', 'start_ms', 'end_ms', 'limit')
_LEGACY_KWARGS = ('tenant_id', 'event_type', 'start_ms', 'end_ms', 'user_id')
def iter_events_range(*, iter_fn: Callable[..., Iterable[dict[str, Any]]], tenant_id: str, event_type: str, start_ms: int, end_ms: int, limit: int) -> Iterable[dict[str, Any]]:
    if _accepts_keywords(iter_fn, _FULL_KWARGS):
        yield from iter_fn(
            tenant_id=str(tenant_id),
            event_types=(str(event_type),),
            start_ms=int(start_ms),
            end_ms=int(end_ms),
            limit=int(limit),
        )
        return
    if _accepts_keywords(iter_fn, _LEGACY_KWARGS):
        yield from iter_fn(
            tenant_id=str(tenant_id),
            event_type=str(event_type),
            start_ms=int(start_ms),
            end_ms=int(end_ms),
            user_id=None,
        )
        return
    raise TypeError('iter_events provider does not expose a supported signature')


__all__ = ['CANON_GROWTH_EVENT_ITER_CALL', 'iter_events_range']
