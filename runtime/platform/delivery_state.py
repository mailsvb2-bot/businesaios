"""Exactly-once delivery state.

Mutable DB files are forbidden inside the repository. This module stores its
state in a per-user runtime data directory by default (override via
DELIVERY_STATE_DB_PATH).

This module provides both functional helpers and a small OO wrapper
(DeliveryState) for backward compatibility with existing runtime effects code.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections.abc import Mapping

from runtime.platform._delivery_state_codec import merge_metadata as _merge_metadata
from runtime.platform._delivery_state_codec import metadata_json as _metadata_json
from runtime.platform._delivery_state_codec import normalize_receipt_row as _normalize_receipt_row
from runtime.platform.app_paths import runtime_data_dir
from runtime.platform.config.env_flags import env_path
from runtime.platform.delivery_state_policy import DEFAULT_DELIVERY_STATE_POLICY
from runtime.platform.outbox.sqlite_pragmas import configure_sqlite, is_prod_env

FINALIZED_PHASE = DEFAULT_DELIVERY_STATE_POLICY.finalized_phase
ACCEPTED_PHASE = DEFAULT_DELIVERY_STATE_POLICY.accepted_phase
RECOVERY_PHASE = DEFAULT_DELIVERY_STATE_POLICY.recovery_phase


def _default_db_path() -> Path:
    return runtime_data_dir() / "delivery_state.db"


def _get_db_path() -> Path:
    return env_path("DELIVERY_STATE_DB_PATH", str(_default_db_path()))


def _ensure_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    configure_sqlite(conn, prod=is_prod_env())
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS delivery_state (
                message_id TEXT PRIMARY KEY,
                delivered_at_ms BIGINT NOT NULL,
                external_id TEXT,
                payload_digest TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                delivery_phase TEXT NOT NULL DEFAULT 'finalized',
                accepted_at_ms BIGINT,
                finalized_at_ms BIGINT
            )
            """
        )
        columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(delivery_state)")}
        if "delivered_at_ms" not in columns:
            conn.execute("ALTER TABLE delivery_state ADD COLUMN delivered_at_ms BIGINT NOT NULL DEFAULT 0")
        if "external_id" not in columns:
            conn.execute("ALTER TABLE delivery_state ADD COLUMN external_id TEXT")
        if "payload_digest" not in columns:
            conn.execute("ALTER TABLE delivery_state ADD COLUMN payload_digest TEXT")
        if "metadata_json" not in columns:
            conn.execute("ALTER TABLE delivery_state ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}' ")
        if "delivery_phase" not in columns:
            conn.execute(f"ALTER TABLE delivery_state ADD COLUMN delivery_phase TEXT NOT NULL DEFAULT '{FINALIZED_PHASE}'")
        if "accepted_at_ms" not in columns:
            conn.execute("ALTER TABLE delivery_state ADD COLUMN accepted_at_ms BIGINT")
        if "finalized_at_ms" not in columns:
            conn.execute("ALTER TABLE delivery_state ADD COLUMN finalized_at_ms BIGINT")
        conn.commit()
    finally:
        conn.close()


def _open_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    configure_sqlite(conn, prod=is_prod_env())
    return conn


def _select_receipt(conn: sqlite3.Connection, message_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT message_id, delivered_at_ms, external_id, payload_digest, metadata_json, delivery_phase, accepted_at_ms, finalized_at_ms FROM delivery_state WHERE message_id = ?",
        (str(message_id),),
    ).fetchone()
    return None if row is None else _normalize_receipt_row(row)


def _fetchall_receipts(conn: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    rows = conn.execute(query, params).fetchall()
    return [_normalize_receipt_row(row) for row in rows]


def is_delivered(message_id: str) -> bool:
    db_path = _get_db_path()
    _ensure_db(db_path)
    conn = _open_connection(db_path)
    try:
        return conn.execute(
            "SELECT 1 FROM delivery_state WHERE message_id = ? AND delivery_phase = ?",
            (message_id, FINALIZED_PHASE),
        ).fetchone() is not None
    finally:
        conn.close()


def get_receipt(message_id: str) -> dict[str, Any] | None:
    db_path = _get_db_path()
    _ensure_db(db_path)
    conn = _open_connection(db_path)
    try:
        return _select_receipt(conn, str(message_id))
    finally:
        conn.close()


def is_accepted(message_id: str) -> bool:
    db_path = _get_db_path()
    _ensure_db(db_path)
    conn = _open_connection(db_path)
    try:
        return conn.execute(
            "SELECT 1 FROM delivery_state WHERE message_id = ? AND delivery_phase = ?",
            (message_id, ACCEPTED_PHASE),
        ).fetchone() is not None
    finally:
        conn.close()


def list_inflight_receipts(*, limit: int = DEFAULT_DELIVERY_STATE_POLICY.default_list_limit) -> list[dict[str, Any]]:
    db_path = _get_db_path()
    _ensure_db(db_path)
    conn = _open_connection(db_path)
    try:
        return _fetchall_receipts(
            conn,
            "SELECT message_id, delivered_at_ms, external_id, payload_digest, metadata_json, delivery_phase, accepted_at_ms, finalized_at_ms FROM delivery_state WHERE delivery_phase != ? ORDER BY COALESCE(accepted_at_ms, delivered_at_ms) ASC, message_id ASC LIMIT ?",
            (FINALIZED_PHASE, DEFAULT_DELIVERY_STATE_POLICY.normalize_limit(limit)),
        )
    finally:
        conn.close()


def list_stale_accepted_receipts(*, older_than_ms: int, limit: int = DEFAULT_DELIVERY_STATE_POLICY.default_list_limit, now_ms: int | None = None) -> list[dict[str, Any]]:
    threshold_ms = DEFAULT_DELIVERY_STATE_POLICY.normalize_stale_threshold_ms(older_than_ms)
    moment_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    cutoff_ms = max(0, moment_ms - threshold_ms)
    db_path = _get_db_path()
    _ensure_db(db_path)
    conn = _open_connection(db_path)
    try:
        return _fetchall_receipts(
            conn,
            """
            SELECT message_id, delivered_at_ms, external_id, payload_digest, metadata_json, delivery_phase, accepted_at_ms, finalized_at_ms
            FROM delivery_state
            WHERE delivery_phase = ?
              AND COALESCE(accepted_at_ms, delivered_at_ms) <= ?
            ORDER BY COALESCE(accepted_at_ms, delivered_at_ms) ASC, message_id ASC
            LIMIT ?
            """,
            (ACCEPTED_PHASE, cutoff_ms, DEFAULT_DELIVERY_STATE_POLICY.normalize_limit(limit)),
        )
    finally:
        conn.close()


def mark_accepted(
    message_id: str,
    *,
    external_id: str | None = None,
    payload_digest: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    db_path = _get_db_path()
    _ensure_db(db_path)
    conn = _open_connection(db_path)
    now_ms = int(time.time() * 1000)
    try:
        existing = conn.execute("SELECT metadata_json FROM delivery_state WHERE message_id = ?", (str(message_id),)).fetchone()
        merged_metadata = _merge_metadata(existing[0] if existing is not None else None, {**dict(metadata or {}), "delivery_phase": ACCEPTED_PHASE})
        metadata_json = _metadata_json(merged_metadata)
        conn.execute(
            """
            INSERT INTO delivery_state(message_id, delivered_at_ms, external_id, payload_digest, metadata_json, delivery_phase, accepted_at_ms, finalized_at_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(message_id) DO UPDATE SET
                delivered_at_ms = delivery_state.delivered_at_ms,
                external_id = COALESCE(delivery_state.external_id, excluded.external_id),
                payload_digest = COALESCE(delivery_state.payload_digest, excluded.payload_digest),
                metadata_json = ?,
                delivery_phase = CASE
                    WHEN delivery_state.delivery_phase = ? THEN ?
                    ELSE ?
                END,
                accepted_at_ms = COALESCE(delivery_state.accepted_at_ms, excluded.accepted_at_ms),
                finalized_at_ms = delivery_state.finalized_at_ms
            """,
            (
                str(message_id),
                now_ms,
                None if external_id is None else str(external_id),
                None if payload_digest is None else str(payload_digest),
                metadata_json,
                ACCEPTED_PHASE,
                now_ms,
                metadata_json,
                FINALIZED_PHASE,
                FINALIZED_PHASE,
                ACCEPTED_PHASE,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def mark_recovery_queued(
    message_id: str,
    *,
    payload_digest: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    now_ms: int | None = None,
) -> dict[str, Any] | None:
    db_path = _get_db_path()
    _ensure_db(db_path)
    conn = _open_connection(db_path)
    moment_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    try:
        row = conn.execute(
            "SELECT metadata_json, accepted_at_ms, external_id, payload_digest, delivery_phase, finalized_at_ms FROM delivery_state WHERE message_id = ?",
            (str(message_id),),
        ).fetchone()
        if row is None:
            return None
        if str(row[4] or FINALIZED_PHASE) == FINALIZED_PHASE:
            return _select_receipt(conn, str(message_id))
        merged_metadata = _merge_metadata(
            row[0],
            {
                **dict(metadata or {}),
                "delivery_phase": RECOVERY_PHASE,
                "recovery": True,
                "recovery_attempts": int(_merge_metadata(row[0], {}).get("recovery_attempts") or 0) + 1,
                "last_recovery_at_ms": moment_ms,
            },
        )
        metadata_json = _metadata_json(merged_metadata)
        conn.execute(
            """
            UPDATE delivery_state
            SET payload_digest = COALESCE(payload_digest, ?),
                metadata_json = ?,
                delivery_phase = ?,
                accepted_at_ms = COALESCE(accepted_at_ms, ?),
                finalized_at_ms = finalized_at_ms
            WHERE message_id = ?
            """,
            (
                None if payload_digest is None else str(payload_digest),
                metadata_json,
                RECOVERY_PHASE,
                moment_ms,
                str(message_id),
            ),
        )
        conn.commit()
        return _select_receipt(conn, str(message_id))
    finally:
        conn.close()


def mark_delivered(
    message_id: str,
    *,
    external_id: str | None = None,
    payload_digest: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    db_path = _get_db_path()
    _ensure_db(db_path)
    conn = _open_connection(db_path)
    now_ms = int(time.time() * 1000)
    try:
        existing = conn.execute("SELECT metadata_json, accepted_at_ms FROM delivery_state WHERE message_id = ?", (str(message_id),)).fetchone()
        merged_metadata = _merge_metadata(existing[0] if existing is not None else None, {**dict(metadata or {}), "delivery_phase": FINALIZED_PHASE})
        metadata_json = _metadata_json(merged_metadata)
        accepted_at_ms = None if existing is None else existing[1]
        conn.execute(
            """
            INSERT INTO delivery_state(message_id, delivered_at_ms, external_id, payload_digest, metadata_json, delivery_phase, accepted_at_ms, finalized_at_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(message_id) DO UPDATE SET
                delivered_at_ms = excluded.delivered_at_ms,
                external_id = COALESCE(delivery_state.external_id, excluded.external_id),
                payload_digest = COALESCE(delivery_state.payload_digest, excluded.payload_digest),
                metadata_json = ?,
                delivery_phase = ?,
                accepted_at_ms = COALESCE(delivery_state.accepted_at_ms, excluded.accepted_at_ms),
                finalized_at_ms = excluded.finalized_at_ms
            """,
            (
                str(message_id),
                now_ms,
                None if external_id is None else str(external_id),
                None if payload_digest is None else str(payload_digest),
                metadata_json,
                FINALIZED_PHASE,
                accepted_at_ms if accepted_at_ms is not None else now_ms,
                now_ms,
                metadata_json,
                FINALIZED_PHASE,
            ),
        )
        conn.commit()
    finally:
        conn.close()


@dataclass
class DeliveryState:
    """Backward-compatible wrapper."""

    db_path: Path | None = None

    def _path(self) -> Path:
        return self.db_path or _get_db_path()

    def _call(self, fn_name: str, *args: Any, **kwargs: Any) -> Any:
        path = self._path()
        _ensure_db(path)
        original = _get_db_path
        try:
            globals()["_get_db_path"] = lambda: path
            return globals()[fn_name](*args, **kwargs)
        finally:
            globals()["_get_db_path"] = original

    def is_delivered(self, message_id: str) -> bool:
        return bool(self._call("is_delivered", message_id))

    def is_accepted(self, message_id: str) -> bool:
        return bool(self._call("is_accepted", message_id))

    def list_inflight_receipts(self, *, limit: int = DEFAULT_DELIVERY_STATE_POLICY.default_list_limit) -> list[dict[str, Any]]:
        return list(self._call("list_inflight_receipts", limit=limit))

    def list_stale_accepted_receipts(self, *, older_than_ms: int, limit: int = DEFAULT_DELIVERY_STATE_POLICY.default_list_limit, now_ms: int | None = None) -> list[dict[str, Any]]:
        return list(self._call("list_stale_accepted_receipts", older_than_ms=older_than_ms, limit=limit, now_ms=now_ms))

    def get_receipt(self, message_id: str) -> dict[str, Any] | None:
        receipt = self._call("get_receipt", message_id)
        return dict(receipt) if isinstance(receipt, Mapping) else receipt

    def mark_accepted(self, message_id: str, *, external_id: str | None = None, payload_digest: str | None = None, metadata: Mapping[str, Any] | None = None) -> None:
        self._call("mark_accepted", message_id, external_id=external_id, payload_digest=payload_digest, metadata=metadata)

    def mark_recovery_queued(self, message_id: str, *, payload_digest: str | None = None, metadata: Mapping[str, Any] | None = None, now_ms: int | None = None) -> dict[str, Any] | None:
        receipt = self._call("mark_recovery_queued", message_id, payload_digest=payload_digest, metadata=metadata, now_ms=now_ms)
        return dict(receipt) if isinstance(receipt, Mapping) else receipt

    def mark_delivered(self, message_id: str, *, external_id: str | None = None, payload_digest: str | None = None, metadata: Mapping[str, Any] | None = None) -> None:
        self._call("mark_delivered", message_id, external_id=external_id, payload_digest=payload_digest, metadata=metadata)


@contextmanager
def open_delivery_state(db_path: str | Path | None = None):
    """Context-managed delivery state owner used by runtime bootstrap.

    This keeps a single canonical delivery-state implementation while preserving
    the existing ``open_delivery_state(...)`` bootstrap contract expected by the
    runtime system builder.
    """
    state = DeliveryState(db_path=Path(db_path) if db_path is not None else None)
    yield state


__all__ = [name for name in globals() if not name.startswith("_")]
