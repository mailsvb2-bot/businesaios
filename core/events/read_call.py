from __future__ import annotations

"""Canonical read-call discipline for event stores.

Prevents false fallback behavior where an internal ``TypeError`` from the
store implementation could be mistaken for a signature mismatch.
"""

from typing import Any, Callable
from collections.abc import Iterable

from core.utils.call_signature import accepted_kwargs as _accepted_kwargs
from core.utils.call_signature import accepts_keyword as _accepts_keyword
from core.utils.call_signature import supports_zero_arg_call as _supports_zero_arg_call

CANON_EVENT_READ_CALL_DISCIPLINE = True


def call_latest_events(
    *,
    latest_fn: Callable[..., Iterable[dict[str, Any]]],
    tenant_id: str,
    event_types: tuple[str, ...],
    limit: int,
    user_id: str | None = None,
    legacy_event_type: str | None = None,
) -> Iterable[dict[str, Any]]:
    full_kwargs = _accepted_kwargs(
        latest_fn,
        {
            'tenant_id': str(tenant_id),
            'user_id': None if user_id is None else str(user_id),
            'event_types': tuple(str(item) for item in event_types),
            'limit': int(limit),
        },
    )
    if 'event_types' in full_kwargs:
        return latest_fn(**full_kwargs)

    if _accepts_keyword(latest_fn, 'event_type'):
        fallback_event_type = str(legacy_event_type or (event_types[0] if event_types else ''))
        legacy_kwargs = _accepted_kwargs(
            latest_fn,
            {
                'tenant_id': str(tenant_id),
                'user_id': None if user_id is None else str(user_id),
                'event_type': fallback_event_type,
                'limit': int(limit),
            },
        )
        return latest_fn(**legacy_kwargs)

    raise TypeError('latest_events provider does not expose a supported signature')


def call_iter_events(
    *,
    iter_fn: Callable[..., Iterable[dict[str, Any]]],
    tenant_id: str,
    event_types: tuple[str, ...] = (),
    start_ms: int | None = None,
    end_ms: int | None = None,
    limit: int | None = None,
    user_id: str | None = None,
    allow_zero_arg_fallback: bool = False,
) -> Iterable[dict[str, Any]]:
    full_kwargs = _accepted_kwargs(
        iter_fn,
        {
            'tenant_id': str(tenant_id),
            'event_types': tuple(str(item) for item in event_types),
            'start_ms': None if start_ms is None else int(start_ms),
            'end_ms': None if end_ms is None else int(end_ms),
            'limit': None if limit is None else int(limit),
            'user_id': None if user_id is None else str(user_id),
        },
    )
    if not event_types or 'event_types' in full_kwargs:
        return iter_fn(**full_kwargs)

    if _accepts_keyword(iter_fn, 'event_type'):
        legacy_kwargs = _accepted_kwargs(
            iter_fn,
            {
                'tenant_id': str(tenant_id),
                'event_type': str(event_types[0]),
                'start_ms': None if start_ms is None else int(start_ms),
                'end_ms': None if end_ms is None else int(end_ms),
                'user_id': None if user_id is None else str(user_id),
                'limit': None if limit is None else int(limit),
            },
        )
        return iter_fn(**legacy_kwargs)

    if allow_zero_arg_fallback and _supports_zero_arg_call(iter_fn):
        return iter_fn()

    raise TypeError('iter_events provider does not expose a supported signature')


def call_latest_event(
    *,
    latest_fn: Callable[..., dict[str, Any] | None],
    tenant_id: str = "default",
    event_types: tuple[str, ...] = (),
    user_id: str | None = None,
    legacy_event_type: str | None = None,
) -> dict[str, Any] | None:
    full_kwargs = _accepted_kwargs(
        latest_fn,
        {
            'tenant_id': str(tenant_id),
            'user_id': None if user_id is None else str(user_id),
            'event_types': tuple(str(item) for item in event_types) if event_types else None,
        },
    )
    if not event_types or 'event_types' in full_kwargs:
        return latest_fn(**full_kwargs)

    if _accepts_keyword(latest_fn, 'event_type'):
        fallback_event_type = str(legacy_event_type or (event_types[0] if event_types else ''))
        legacy_kwargs = _accepted_kwargs(
            latest_fn,
            {
                'tenant_id': str(tenant_id),
                'user_id': None if user_id is None else str(user_id),
                'event_type': fallback_event_type,
            },
        )
        return latest_fn(**legacy_kwargs)

    raise TypeError('latest_event provider does not expose a supported signature')


__all__ = [
    'CANON_EVENT_READ_CALL_DISCIPLINE',
    'call_iter_events',
    'call_latest_event',
    'call_latest_events',
]
