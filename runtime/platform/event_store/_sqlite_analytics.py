"""SQLite analytics queries — pure DB-side functions.

All functions take an open sqlite3.Connection as first argument.
SqliteEventStore delegates to these; they have NO class dependencies.
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from observability.platform.observability.silent import swallow as _swallow


# ── helpers ──────────────────────────────────────────────────────────────────

MAX_I64 = 2**63 - 1


def _excl_end(end_ms: Optional[int]) -> int:
    now = int(time.time() * 1000)
    if end_ms is None:
        return min(now + 1, MAX_I64)
    try:
        e = int(end_ms)
    except Exception:
        return min(now + 1, MAX_I64)
    return MAX_I64 if e >= MAX_I64 else e + 1


def _req_tenant(tenant_id: str) -> str:
    tid = str(tenant_id or "").strip()
    if not tid:
        raise ValueError("tenant_id is required (strict)")
    return tid


# ── analytics functions ───────────────────────────────────────────────────────

def count_distinct_users(
    db,
    *,
    tenant_id: str,
    start_ms: int,
    end_ms: Optional[int] = None,
    event_type: Optional[str] = None,
    exclude_system: bool = True,
) -> int:
    """Count distinct user_ids in a time window."""
    tid = _req_tenant(tenant_id)
    end = _excl_end(end_ms)
    q = (
        "SELECT COUNT(DISTINCT user_id) FROM events "
        "WHERE tenant_id=? AND timestamp_ms>=? AND timestamp_ms<?"
    )
    params: list[Any] = [tid, int(start_ms), end]
    if event_type:
        q += " AND event_type=?"
        params.append(str(event_type))
    if exclude_system:
        q += " AND user_id IS NOT NULL AND user_id!='system'"
    row = db.execute(q, tuple(params)).fetchone()
    try:
        return int(row[0] or 0) if row else 0
    except Exception:
        return 0


def recent_user_ids(
    db,
    *,
    tenant_id: str,
    start_ms: int = 0,
    end_ms: Optional[int] = None,
    limit: int = 20,
    exclude_system: bool = True,
) -> list[tuple[str, int]]:
    """Most recently active (user_id, last_ts_ms) pairs, desc."""
    tid = _req_tenant(tenant_id)
    end = _excl_end(end_ms)
    lim = max(1, min(int(limit), 500))
    q = (
        "SELECT user_id, MAX(timestamp_ms) AS last_ts "
        "FROM events WHERE tenant_id=? AND timestamp_ms>=? AND timestamp_ms<?"
    )
    params: list[Any] = [tid, int(start_ms), end]
    if exclude_system:
        q += " AND user_id IS NOT NULL AND user_id!='system'"
    q += " GROUP BY user_id ORDER BY last_ts DESC, user_id ASC LIMIT ?"
    params.append(lim)
    rows = db.execute(q, tuple(params)).fetchall()
    out: list[tuple[str, int]] = []
    for r in rows or []:
        try:
            uid = str(r[0] or "").strip()
            if uid:
                out.append((uid, int(r[1] or 0)))
        except Exception:
            continue
    return out


def count_events(
    db,
    *,
    tenant_id: str,
    event_type: str,
    start_ms: int = 0,
    end_ms: Optional[int] = None,
    user_id: Optional[str] = None,
) -> int:
    """Count events of a type in a time window."""
    tid = _req_tenant(tenant_id)
    end = _excl_end(end_ms)
    q = (
        "SELECT COUNT(1) FROM events "
        "WHERE tenant_id=? AND event_type=? AND timestamp_ms>=? AND timestamp_ms<?"
    )
    params: list[Any] = [tid, str(event_type), int(start_ms), end]
    if user_id is not None:
        q += " AND user_id=?"
        params.append(str(user_id))
    row = db.execute(q, tuple(params)).fetchone()
    try:
        return int(row[0] or 0) if row else 0
    except Exception:
        return 0


def get_counter(db, *, event_type: str, user_id: Optional[str] = None) -> int:
    """Return incremental counter (fast path over full scan)."""
    uid = "__all__" if user_id is None else str(user_id)
    row = db.execute(
        "SELECT cnt FROM event_counters WHERE event_type=? AND user_id=?",
        (str(event_type), uid),
    ).fetchone()
    try:
        return int(row[0] or 0) if row else 0
    except Exception:
        return 0


def sum_event_payload_int(
    db,
    *,
    tenant_id: str,
    event_type: str,
    field: str,
    start_ms: int = 0,
    end_ms: Optional[int] = None,
    user_id: Optional[str] = None,
) -> int:
    """Sum an integer field from payload_json. Tries JSON1, falls back to app-side."""
    tid = _req_tenant(tenant_id)
    end = _excl_end(end_ms)
    et = str(event_type)
    fld = str(field)

    try:
        q = (
            "SELECT SUM(CAST(json_extract(payload_json, ?) AS INTEGER)) "
            "FROM events WHERE tenant_id=? AND event_type=? AND timestamp_ms>=? AND timestamp_ms<?"
        )
        params: list[Any] = [f"$.{fld}", tid, et, int(start_ms), end]
        if user_id is not None:
            q += " AND user_id=?"
            params.append(str(user_id))
        row = db.execute(q, tuple(params)).fetchone()
        if row and row[0] is not None:
            return int(row[0] or 0)
    except Exception:
        _swallow("_sqlite_analytics", "sum_event_payload_int.json1_fallback")

    total = 0
    q2 = (
        "SELECT payload_json FROM events "
        "WHERE tenant_id=? AND event_type=? AND timestamp_ms>=? AND timestamp_ms<?"
    )
    p2: list[Any] = [tid, et, int(start_ms), end]
    if user_id is not None:
        q2 += " AND user_id=?"
        p2.append(str(user_id))
    for (pj,) in db.execute(q2, tuple(p2)).fetchall() or []:
        try:
            obj = json.loads(pj or "{}")
            total += int(obj.get(fld) or 0)
        except Exception:
            continue
    return int(total)


def count_active_users_min_days(
    db,
    *,
    tenant_id: str,
    lookback_days: int,
    min_active_days: int = 2,
) -> int:
    """Users with ≥ min_active_days distinct activity days in the last N days."""
    lbd = max(1, min(int(lookback_days), 365))
    mad = max(1, min(int(min_active_days), 30))
    now_ms = int(time.time() * 1000)
    start_ms = max(0, now_ms - lbd * 24 * 3600 * 1000)
    tid = _req_tenant(tenant_id)
    q = (
        "SELECT COUNT(1) FROM ("
        "  SELECT user_id, COUNT(DISTINCT strftime('%Y-%m-%d', timestamp_ms/1000, 'unixepoch')) AS d "
        "  FROM events "
        "  WHERE tenant_id=? AND timestamp_ms>=? AND timestamp_ms<? "
        "  AND user_id IS NOT NULL AND user_id!='system' "
        "  GROUP BY user_id "
        "  HAVING d>=?"
        ")"
    )
    row = db.execute(q, (tid, int(start_ms), int(now_ms), int(mad))).fetchone()
    try:
        return int(row[0] or 0) if row else 0
    except Exception:
        return 0


def count_events_payload_like(
    db,
    *,
    tenant_id: str,
    event_type: str,
    payload_substring: str,
    start_ms: int = 0,
    end_ms: Optional[int] = None,
) -> int:
    """Best-effort analytics: events where payload_json LIKE %substring%."""
    end = _excl_end(end_ms)
    q = (
        "SELECT COUNT(1) FROM events "
        "WHERE timestamp_ms>=? AND timestamp_ms<? AND event_type=? AND payload_json LIKE ?"
    )
    row = db.execute(q, (int(start_ms), end, str(event_type), f"%{payload_substring}%")).fetchone()
    return int(row[0] or 0)


def count_distinct_users_payload_like(
    db,
    *,
    tenant_id: str,
    event_type: str,
    payload_substring: str,
    start_ms: int = 0,
    end_ms: Optional[int] = None,
) -> int:
    """Distinct user count where payload_json LIKE %substring%."""
    end = _excl_end(end_ms)
    q = (
        "SELECT COUNT(DISTINCT user_id) FROM events "
        "WHERE user_id IS NOT NULL AND user_id!='system' "
        "AND timestamp_ms>=? AND timestamp_ms<? AND event_type=? AND payload_json LIKE ?"
    )
    row = db.execute(q, (int(start_ms), end, str(event_type), f"%{payload_substring}%")).fetchone()
    return int(row[0] or 0)
