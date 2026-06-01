from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

from observability.platform.observability.silent import swallow
from runtime.platform.config.env_flags import env_int
from runtime.platform.outbox.sqlite_pragmas import configure_sqlite, is_prod_env

DDL = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS payment_outbox (
  id TEXT PRIMARY KEY,
  dedupe_key TEXT UNIQUE,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at_ms BIGINT NOT NULL,
  updated_at_ms BIGINT NOT NULL,
  run_after_ms BIGINT NOT NULL,
  attempts INT NOT NULL DEFAULT 0,
  last_error TEXT
);
CREATE INDEX IF NOT EXISTS idx_payment_outbox_status_after ON payment_outbox(status, run_after_ms);

CREATE TABLE IF NOT EXISTS payment_terminal (
  external_id TEXT PRIMARY KEY,
  terminal_status TEXT NOT NULL,
  emitted_at_ms BIGINT NOT NULL,
  notification_id TEXT,
  event TEXT
);
CREATE INDEX IF NOT EXISTS idx_payment_terminal_status ON payment_terminal(terminal_status);
"""


class SqlitePaymentOutbox:
    """Durable job outbox for external payment reconciliations (SQLite)."""

    def __init__(self, path: str):
        self._path = str(path)
        self._conn: sqlite3.Connection | None = None

        # Inflight lease (ms): if worker crashes, jobs are re-queued after this time.
        try:
            self._lease_ms = int(env_int("PAYMENT_OUTBOX_LEASE_MS", 60000, lo=5_000, hi=10 * 60_000))
        except (TypeError, ValueError):
            self._lease_ms = 60000
        self._lease_ms = max(5_000, min(10 * 60_000, int(self._lease_ms)))

    def __enter__(self) -> SqlitePaymentOutbox:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        configure_sqlite(self._conn, prod=is_prod_env())
        self._conn.executescript(DDL)
        self._conn.commit()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def ping(self) -> bool:
        try:
            assert self._conn is not None
            self._conn.execute("SELECT 1")
            return True
        except (AssertionError, sqlite3.Error):
            return False

    def enqueue_once(self, *, dedupe_key: str, payload: dict[str, Any]) -> str:
        assert self._conn is not None
        now = int(time.time() * 1000)
        jid = str(uuid.uuid4())
        try:
            self._conn.execute(
                "INSERT INTO payment_outbox(id, dedupe_key, status, payload_json, created_at_ms, updated_at_ms, run_after_ms, attempts) VALUES(?,?,?,?,?,?,?,0)",
                (jid, str(dedupe_key), "pending", json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":")), now, now, now),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            pass
        cur = self._conn.execute("SELECT id FROM payment_outbox WHERE dedupe_key=? LIMIT 1", (str(dedupe_key),))
        row = cur.fetchone()
        return str(row[0]) if row else jid

    def list_pending(self, *, limit: int = 50) -> list[dict[str, Any]]:
        assert self._conn is not None
        now = int(time.time() * 1000)
        # Reap stale inflight jobs back to pending (crash-safe lease).
        try:
            cutoff = now - int(self._lease_ms)
            self._conn.execute(
                "UPDATE payment_outbox SET status='pending', updated_at_ms=? "
                "WHERE status='inflight' AND updated_at_ms <= ?",
                (now, int(cutoff)),
            )
            self._conn.commit()
        except sqlite3.Error:
            swallow(__name__, 'runtime/platform/outbox/sqlite_payment_outbox.py', extra={"phase": "reap_inflight"})
        cur = self._conn.execute(
            "SELECT id, dedupe_key, payload_json, attempts, run_after_ms FROM payment_outbox WHERE status='pending' AND run_after_ms <= ? ORDER BY run_after_ms ASC LIMIT ?",
            (now, int(limit)),
        )
        rows = cur.fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": r[0],
                    "dedupe_key": r[1],
                    "payload": json.loads(r[2] or "{}"),
                    "attempts": int(r[3] or 0),
                    "run_after_ms": int(r[4] or 0),
                }
            )
        return out

    def claim(self, job_id: str) -> bool:
        assert self._conn is not None
        now = int(time.time() * 1000)
        cur = self._conn.execute(
            "UPDATE payment_outbox SET status='inflight', updated_at_ms=? WHERE id=? AND status='pending'",
            (now, str(job_id)),
        )
        self._conn.commit()
        return int(cur.rowcount or 0) == 1

    def mark_delivered(self, job_id: str) -> None:
        assert self._conn is not None
        now = int(time.time() * 1000)
        self._conn.execute("UPDATE payment_outbox SET status='delivered', updated_at_ms=? WHERE id=?", (now, str(job_id)))
        self._conn.commit()

    def schedule_retry(self, job_id: str, *, after_ms: int, error: str | None = None) -> None:
        assert self._conn is not None
        now = int(time.time() * 1000)
        run_after = now + int(after_ms)
        self._conn.execute(
            "UPDATE payment_outbox SET status='pending', updated_at_ms=?, run_after_ms=?, attempts=attempts+1, last_error=? WHERE id=?",
            (now, run_after, str(error) if error else None, str(job_id)),
        )
        self._conn.commit()

    def move_to_dead_letter(self, job_id: str, *, error: str | None = None) -> None:
        assert self._conn is not None
        now = int(time.time() * 1000)
        self._conn.execute(
            "UPDATE payment_outbox SET status='dead', updated_at_ms=?, last_error=? WHERE id=?",
            (now, str(error) if error else None, str(job_id)),
        )
        self._conn.commit()

    # ---- terminal idempotency (heavy-load safe) ----

    def terminal_status(self, external_id: str) -> str | None:
        """Return terminal_status if already emitted for external_id."""
        assert self._conn is not None
        cur = self._conn.execute(
            "SELECT terminal_status FROM payment_terminal WHERE external_id=? LIMIT 1",
            (str(external_id),),
        )
        row = cur.fetchone()
        return str(row[0]) if row and row[0] is not None else None

    def try_mark_terminal_emitted(
        self,
        *,
        external_id: str,
        terminal_status: str,
        notification_id: str | None = None,
        event: str | None = None,
    ) -> bool:
        """Idempotently mark terminal outcome emission.

        Returns True iff this call created the marker (i.e., caller should emit terminal events).
        """
        assert self._conn is not None
        now = int(time.time() * 1000)
        try:
            self._conn.execute(
                "INSERT INTO payment_terminal(external_id, terminal_status, emitted_at_ms, notification_id, event) VALUES(?,?,?,?,?)",
                (str(external_id), str(terminal_status), now, (str(notification_id) if notification_id else None), (str(event) if event else None)),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
