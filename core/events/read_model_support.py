from __future__ import annotations

"""Best-effort event-store helpers for read models.

These helpers sit *above* the strict signature-safe helpers in
``core.events.read_call``.

Why this layer exists:
- read models often need a valid fallback path and may not raise;
- that best-effort policy should not be reimplemented in every read model;
- failures should stay observable instead of becoming silent broad-except blocks.
"""

from typing import Any, Iterable

from core.events.read_call import call_iter_events, call_latest_event, call_latest_events
from core.observability.silent import swallow

CANON_EVENT_READ_MODEL_SUPPORT = True


def best_effort_latest_event(
    *,
    event_store: Any,
    where: str,
    tenant_id: str = "default",
    user_id: str | None = None,
    event_types: tuple[str, ...] = (),
    legacy_event_type: str | None = None,
) -> dict[str, Any] | None:
    latest_fn = getattr(event_store, 'latest_event', None)
    if latest_fn is None:
        return None
    try:
        return call_latest_event(
            latest_fn=latest_fn,
            tenant_id=str(tenant_id),
            user_id=None if user_id is None else str(user_id),
            event_types=tuple(str(item) for item in event_types),
            legacy_event_type=legacy_event_type,
        )
    except Exception:
        swallow(__name__, where)
        return None


def best_effort_latest_events(
    *,
    event_store: Any,
    where: str,
    tenant_id: str,
    user_id: str | None = None,
    event_types: tuple[str, ...],
    legacy_event_type: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    latest_fn = getattr(event_store, 'latest_events', None)
    if latest_fn is None:
        return []
    try:
        return list(
            call_latest_events(
                latest_fn=latest_fn,
                tenant_id=str(tenant_id),
                user_id=None if user_id is None else str(user_id),
                event_types=tuple(str(item) for item in event_types),
                legacy_event_type=legacy_event_type,
                limit=int(limit),
            )
        )
    except Exception:
        swallow(__name__, where)
        return []


def best_effort_iter_events(
    *,
    event_store: Any,
    where: str,
    tenant_id: str,
    event_types: tuple[str, ...] = (),
    start_ms: int | None = None,
    end_ms: int | None = None,
    limit: int | None = None,
    user_id: str | None = None,
    allow_zero_arg_fallback: bool = False,
) -> list[dict[str, Any]]:
    iter_fn = getattr(event_store, 'iter_events', None)
    if iter_fn is None:
        return []
    try:
        return list(
            call_iter_events(
                iter_fn=iter_fn,
                tenant_id=str(tenant_id),
                event_types=tuple(str(item) for item in event_types),
                start_ms=start_ms,
                end_ms=end_ms,
                limit=limit,
                user_id=None if user_id is None else str(user_id),
                allow_zero_arg_fallback=allow_zero_arg_fallback,
            )
        )
    except Exception:
        swallow(__name__, where)
        return []


__all__ = [
    'CANON_EVENT_READ_MODEL_SUPPORT',
    'best_effort_iter_events',
    'best_effort_latest_event',
    'best_effort_latest_events',
]
