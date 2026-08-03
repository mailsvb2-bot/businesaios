"""Canonical SQLite read-query surface for ``SqliteEventStore``."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from typing import Any

from .sqlite_helpers import _exclusive_end_ms, _row_to_event

EVENT_COLUMNS = (
    "event_id,tenant_id,user_id,source,event_type,timestamp_ms,"
    "decision_id,correlation_id,payload_json"
)


def _sequence_expression(db: sqlite3.Connection) -> str:
    """Use durable append_seq when migrated; support legacy direct connections."""

    columns = {
        str(row[1]).strip().lower()
        for row in db.execute("PRAGMA table_info(events)").fetchall()
    }
    return "append_seq" if "append_seq" in columns else "rowid"


def _literal_like_pattern(value: object) -> str:
    escaped = str(value).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _normalized_event_types(
    *, event_type: str | None, event_types: Sequence[str] | None
) -> tuple[str, ...]:
    normalized = tuple(
        dict.fromkeys(
            str(item).strip()
            for item in (event_types or ())
            if str(item).strip()
        )
    )
    if normalized:
        return normalized
    singular = str(event_type or "").strip()
    return (singular,) if singular else ()


def _iter_rows(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    start_ms: int = 0,
    end_ms: int | None = None,
    after_append_seq: int | None = None,
    event_type: str | None = None,
    event_types: Sequence[str] | None = None,
    user_id: str | None = None,
    order_by: str | None = None,
    limit: int | None = None,
) -> Sequence[sqlite3.Row | tuple]:
    sequence = _sequence_expression(db)
    columns = (
        f"{sequence} AS append_seq,{EVENT_COLUMNS}"
        if after_append_seq is not None
        else EVENT_COLUMNS
    )
    sql = [
        f"SELECT {columns} FROM events "
        "WHERE tenant_id=? AND timestamp_ms>=? AND timestamp_ms<?"
    ]
    params: list[object] = [
        str(tenant_id),
        int(start_ms),
        _exclusive_end_ms(end_ms),
    ]
    if after_append_seq is not None:
        sql.append(f"AND {sequence}>?")
        params.append(max(0, int(after_append_seq)))
    types = _normalized_event_types(
        event_type=event_type,
        event_types=event_types,
    )
    if len(types) == 1:
        sql.append("AND event_type=?")
        params.append(types[0])
    elif types:
        placeholders = ",".join("?" for _ in types)
        sql.append(f"AND event_type IN ({placeholders})")
        params.extend(types)
    if user_id is not None:
        sql.append("AND user_id=?")
        params.append(str(user_id))
    ordering = order_by or (
        f"{sequence} ASC"
        if after_append_seq is not None
        else f"timestamp_ms ASC, {sequence} ASC"
    )
    sql.append(f"ORDER BY {ordering}")
    if limit is not None:
        sql.append("LIMIT ?")
        params.append(max(1, int(limit)))
    return db.execute(" ".join(sql), tuple(params)).fetchall()


def iter_events(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    start_ms: int = 0,
    end_ms: int | None = None,
    after_append_seq: int | None = None,
    event_type: str | None = None,
    event_types: Sequence[str] | None = None,
    user_id: str | None = None,
    limit: int | None = None,
) -> Iterable[dict[str, Any]]:
    rows = _iter_rows(
        db,
        tenant_id=tenant_id,
        start_ms=start_ms,
        end_ms=end_ms,
        after_append_seq=after_append_seq,
        event_type=event_type,
        event_types=event_types,
        user_id=user_id,
        limit=limit,
    )
    for row in rows:
        yield _row_to_event(row)


def latest_event(
    db: sqlite3.Connection,
    *,
    tenant_id: str = "default",
    user_id: str | None = None,
    event_types: Sequence[str] | None = None,
) -> dict[str, Any] | None:
    sequence = _sequence_expression(db)
    if event_types:
        placeholders = ",".join("?" for _ in event_types)
        sql = (
            f"SELECT {EVENT_COLUMNS} FROM events WHERE tenant_id=? "
            f"AND event_type IN ({placeholders})"
        )
        params: list[object] = [
            str(tenant_id),
            *[str(item) for item in event_types],
        ]
        if user_id is not None:
            sql += " AND user_id=?"
            params.append(str(user_id))
        sql += f" ORDER BY timestamp_ms DESC, {sequence} DESC LIMIT 1"
        row = db.execute(sql, tuple(params)).fetchone()
    else:
        rows = _iter_rows(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            order_by=f"timestamp_ms DESC, {sequence} DESC",
            limit=1,
        )
        row = rows[0] if rows else None
    return _row_to_event(row) if row else None


def latest_events(
    db: sqlite3.Connection,
    *,
    tenant_id: str = "default",
    user_id: str | None = None,
    event_type: str | None = None,
    event_types: Sequence[str] | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    sequence = _sequence_expression(db)
    rows = _iter_rows(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        event_type=event_type,
        event_types=event_types,
        order_by=f"timestamp_ms DESC, {sequence} DESC",
        limit=limit,
    )
    return [_row_to_event(row) for row in rows]


def count_distinct_users(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    start_ms: int,
    end_ms: int | None = None,
    event_type: str | None = None,
    exclude_system: bool = True,
) -> int:
    sql = [
        "SELECT COUNT(DISTINCT user_id) FROM events "
        "WHERE tenant_id=? AND timestamp_ms>=? AND timestamp_ms<?"
    ]
    params: list[object] = [
        str(tenant_id),
        int(start_ms),
        _exclusive_end_ms(end_ms),
    ]
    if event_type is not None:
        sql.append("AND event_type=?")
        params.append(str(event_type))
    if exclude_system:
        sql.append("AND COALESCE(user_id, '') NOT IN ('', 'system')")
    row = db.execute(" ".join(sql), tuple(params)).fetchone()
    return int(row[0] or 0) if row else 0


def recent_user_ids(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    start_ms: int = 0,
    end_ms: int | None = None,
    limit: int = 20,
    exclude_system: bool = True,
) -> list[tuple[str, int]]:
    sql = [
        "SELECT user_id, MAX(timestamp_ms) AS ts FROM events "
        "WHERE tenant_id=? AND timestamp_ms>=? AND timestamp_ms<?"
    ]
    params: list[object] = [
        str(tenant_id),
        int(start_ms),
        _exclusive_end_ms(end_ms),
    ]
    if exclude_system:
        sql.append("AND COALESCE(user_id, '') NOT IN ('', 'system')")
    sql.append("GROUP BY user_id ORDER BY ts DESC, user_id ASC LIMIT ?")
    params.append(int(limit))
    rows = db.execute(" ".join(sql), tuple(params)).fetchall()
    return [
        (str(row[0]), int(row[1]))
        for row in rows
        if row and row[0] is not None
    ]


def count_events(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    event_type: str,
    start_ms: int = 0,
    end_ms: int | None = None,
    user_id: str | None = None,
) -> int:
    sql = [
        "SELECT COUNT(1) FROM events WHERE tenant_id=? AND event_type=? "
        "AND timestamp_ms>=? AND timestamp_ms<?"
    ]
    params: list[object] = [
        str(tenant_id),
        str(event_type),
        int(start_ms),
        _exclusive_end_ms(end_ms),
    ]
    if user_id is not None:
        sql.append("AND user_id=?")
        params.append(str(user_id))
    row = db.execute(" ".join(sql), tuple(params)).fetchone()
    return int(row[0] or 0) if row else 0


def get_counter(
    db: sqlite3.Connection,
    *,
    event_type: str,
    user_id: str | None = None,
) -> int:
    counter_user_id = "__all__" if user_id is None else str(user_id)
    row = db.execute(
        "SELECT cnt FROM event_counters WHERE event_type=? AND user_id=?",
        (str(event_type), counter_user_id),
    ).fetchone()
    return int(row[0] or 0) if row else 0


def sum_event_payload_int(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    event_type: str,
    field: str,
    start_ms: int = 0,
    end_ms: int | None = None,
    user_id: str | None = None,
) -> int:
    total = 0
    for event in iter_events(
        db,
        tenant_id=tenant_id,
        start_ms=start_ms,
        end_ms=end_ms,
        event_type=event_type,
        user_id=user_id,
    ):
        payload = event.get("payload") if isinstance(event, dict) else {}
        try:
            total += int((payload or {}).get(field, 0))
        except Exception:
            continue
    return total


def count_active_users_min_days(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    lookback_days: int,
    min_active_days: int = 2,
) -> int:
    lookback_days = max(1, int(lookback_days))
    min_active_days = max(1, int(min_active_days))
    sql = (
        "SELECT COUNT(1) FROM ("
        "SELECT user_id, COUNT(DISTINCT CAST(timestamp_ms / 86400000 AS INTEGER)) AS active_days "
        "FROM events WHERE tenant_id=? AND COALESCE(user_id, '') NOT IN ('', 'system') "
        "AND timestamp_ms >= (CAST(strftime('%s','now') AS INTEGER) * 1000) - (? * 86400000) "
        "GROUP BY user_id HAVING active_days >= ?"
        ")"
    )
    row = db.execute(
        sql,
        (str(tenant_id), lookback_days, min_active_days),
    ).fetchone()
    return int(row[0] or 0) if row else 0


def count_events_payload_like(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    event_type: str,
    payload_substring: str,
    start_ms: int = 0,
    end_ms: int | None = None,
) -> int:
    row = db.execute(
        "SELECT COUNT(1) FROM events WHERE tenant_id=? AND event_type=? "
        "AND timestamp_ms>=? AND timestamp_ms<? "
        "AND payload_json LIKE ? ESCAPE '\\'",
        (
            str(tenant_id),
            str(event_type),
            int(start_ms),
            _exclusive_end_ms(end_ms),
            _literal_like_pattern(payload_substring),
        ),
    ).fetchone()
    return int(row[0] or 0) if row else 0


def count_distinct_users_payload_like(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    event_type: str,
    payload_substring: str,
    start_ms: int = 0,
    end_ms: int | None = None,
) -> int:
    row = db.execute(
        "SELECT COUNT(DISTINCT user_id) FROM events "
        "WHERE tenant_id=? AND event_type=? "
        "AND timestamp_ms>=? AND timestamp_ms<? "
        "AND payload_json LIKE ? ESCAPE '\\' "
        "AND COALESCE(user_id, '') NOT IN ('', 'system')",
        (
            str(tenant_id),
            str(event_type),
            int(start_ms),
            _exclusive_end_ms(end_ms),
            _literal_like_pattern(payload_substring),
        ),
    ).fetchone()
    return int(row[0] or 0) if row else 0
