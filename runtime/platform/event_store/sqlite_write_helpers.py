"""Write-path helpers for SqliteEventStore append_event.

Responsibility:
  - _append_counters()           — update event_counters incremental table
  - _append_user_state()         — trigger sqlite_user_state projection
"""

from __future__ import annotations


import logging
import sqlite3
from typing import Any

from observability.platform.observability.silent import swallow

logger = logging.getLogger(__name__)


def _append_counters(
    db: sqlite3.Connection,
    *,
    event_type: str,
    user_id: Any,
    ts: int,
) -> None:
    """Increment event_counters rows (best-effort, never raises)."""
    try:
        uid = str(user_id) if user_id is not None else "system"
        for u in (uid, "__all__"):
            db.execute(
                "INSERT INTO event_counters(event_type,user_id,cnt,last_ts_ms) VALUES (?,?,1,?) "
                "ON CONFLICT(event_type,user_id) DO UPDATE SET cnt=cnt+1, last_ts_ms=excluded.last_ts_ms",
                (str(event_type), str(u), int(ts)),
            )
    except Exception as ex:
        logger.warning("event_counters update failed: %r", ex)


def _append_user_state(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    user_id: Any,
    event_type: str,
    ts: int,
    payload_obj: dict,
) -> None:
    """Update user_state read-model projection (best-effort, never raises)."""
    from runtime.platform.event_store.sqlite_user_state import project_user_state

    try:
        project_user_state(
            db,
            tenant_id=tenant_id,
            user_id=str(user_id) if user_id is not None else "",
            event_type=str(event_type),
            ts=int(ts),
            payload_obj=dict(payload_obj),
        )
    except Exception:
        swallow(__name__, "sqlite_write_helpers._append_user_state")
