"""Compatibility facade for the canonical SQLite event-store read queries.

Historically this module carried a second implementation of the analytics
queries.  That duplicated the production path used by ``SqliteEventStore`` and
allowed fixes and tests to diverge from real behaviour.  The canonical
implementation now lives only in :mod:`sqlite_read_queries`; this module keeps
private-import compatibility by re-exporting those exact callables.
"""

from __future__ import annotations

from .sqlite_helpers import MAX_I64, _exclusive_end_ms
from .sqlite_read_queries import (
    count_active_users_min_days,
    count_distinct_users,
    count_distinct_users_payload_like,
    count_events,
    count_events_payload_like,
    get_counter,
    recent_user_ids,
    sum_event_payload_int,
)

# Compatibility alias retained for older internal imports.
_excl_end = _exclusive_end_ms


def _req_tenant(tenant_id: str) -> str:
    """Normalize a required tenant identifier for compatibility callers."""

    normalized = str(tenant_id or "").strip()
    if not normalized:
        raise ValueError("tenant_id is required (strict)")
    return normalized


__all__ = [
    "MAX_I64",
    "_excl_end",
    "_req_tenant",
    "count_active_users_min_days",
    "count_distinct_users",
    "count_distinct_users_payload_like",
    "count_events",
    "count_events_payload_like",
    "get_counter",
    "recent_user_ids",
    "sum_event_payload_int",
]
