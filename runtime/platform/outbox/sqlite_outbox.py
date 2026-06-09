from __future__ import annotations

import os
import sqlite3
import time
from typing import Any

from runtime.platform.config.env_flags import env_int
from runtime.platform.outbox.sqlite_pragmas import configure_sqlite, is_prod_env

MAX_RETRIES = 5


DDL = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  decision_id TEXT NOT NULL,
  correlation_id TEXT NOT NULL,
  action TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at_ms BIGINT NOT NULL,
  delivered_at_ms BIGINT,
  claimed_at_ms BIGINT,
  next_attempt_at_ms BIGINT,
  retry_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  UNIQUE(decision_id)
);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox(status, created_at_ms);
CREATE INDEX IF NOT EXISTS idx_outbox_next_attempt ON outbox(status, next_attempt_at_ms);
"""


class SqliteOutbox:
    """Durable runtime outbox with crash-safe stale-claim recovery.

    Status values:
      - pending     (enqueued, not yet claimed)
      - delivering  (claimed by executor; side-effect may already have happened)
      - delivered   (confirmed delivered)
      - dead        (moved to dead letter)
    """

    def __init__(self, path: str):
        self._path = str(path)
        self._conn: sqlite3.Connection | None = None
        try:
            self._lease_ms = int(env_int("OUTBOX_LEASE_MS", 60_000, lo=5_000, hi=10 * 60_000))
        except (TypeError, ValueError):
            self._lease_ms = 60_000
        self._lease_ms = max(5_000, min(10 * 60_000, int(self._lease_ms)))

    def __enter__(self):
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        configure_sqlite(self._conn, prod=is_prod_env())
        self._conn.executescript(DDL)
        self._conn.commit()
        return self

    def enqueue_once(self, *, decision_id: str, correlation_id: str, action: str, payload_json: str) -> bool:
        assert self._conn is not None
        now_ms = int(time.time() * 1000)
        try:
            self._conn.execute(
                "INSERT INTO outbox(decision_id, correlation_id, action, payload_json, created_at_ms, next_attempt_at_ms, retry_count, status) VALUES(?,?,?,?,?,?,?,?)",
                (decision_id, correlation_id, action, payload_json, now_ms, now_ms, 0, "pending"),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def claim(self, decision_id: str) -> bool:
        """Atomically claim a due message.

        Allows reclaiming stale delivering rows after lease expiry.
        """
        assert self._conn is not None
        now_ms = int(time.time() * 1000)
        stale_cutoff_ms = now_ms - int(self._lease_ms)
        cur = self._conn.execute(
            "UPDATE outbox SET status='delivering', claimed_at_ms=? "
            "WHERE decision_id=? "
            "AND ("
            "    (status='pending' AND (next_attempt_at_ms IS NULL OR next_attempt_at_ms<=?)) "
            " OR (status='delivering' AND claimed_at_ms IS NOT NULL AND claimed_at_ms<=?)"
            ")",
            (now_ms, str(decision_id), now_ms, stale_cutoff_ms),
        )
        self._conn.commit()
        return int(cur.rowcount or 0) == 1

    def mark_delivered(self, decision_id: str) -> None:
        assert self._conn is not None
        self._conn.execute(
            "UPDATE outbox SET status = 'delivered', delivered_at_ms = ?, claimed_at_ms=NULL WHERE decision_id = ? AND status IN ('pending','delivering')",
            (int(time.time() * 1000), str(decision_id)),
        )
        self._conn.commit()

    def _reap_stale_delivering(self) -> None:
        assert self._conn is not None
        now_ms = int(time.time() * 1000)
        stale_cutoff_ms = now_ms - int(self._lease_ms)
        self._conn.execute(
            "UPDATE outbox SET status='pending', claimed_at_ms=NULL "
            "WHERE status='delivering' AND claimed_at_ms IS NOT NULL AND claimed_at_ms<=?",
            (stale_cutoff_ms,),
        )
        self._conn.commit()

    def list_pending(self, *, limit: int = 100) -> list[dict[str, Any]]:
        assert self._conn is not None
        self._reap_stale_delivering()
        cur = self._conn.execute(
            "SELECT decision_id, correlation_id, action, payload_json, created_at_ms, status, retry_count, next_attempt_at_ms, claimed_at_ms "
            "FROM outbox WHERE status IN ('pending','delivering') ORDER BY created_at_ms ASC LIMIT ?",
            (int(limit),),
        )
        rows = cur.fetchall()
        return [
            {
                "decision_id": r[0],
                "correlation_id": r[1],
                "action": r[2],
                "payload_json": r[3],
                "created_at_ms": int(r[4]),
                "status": r[5],
                "retry_count": int(r[6] or 0),
                "next_attempt_at_ms": int(r[7] or 0) if r[7] is not None else None,
                "claimed_at_ms": int(r[8] or 0) if r[8] is not None else None,
            }
            for r in rows
        ]

    def list_claimable(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self.list_pending(limit=limit)

    def get(self, decision_id: str) -> dict[str, Any] | None:
        assert self._conn is not None
        cur = self._conn.execute(
            "SELECT decision_id, correlation_id, action, payload_json, created_at_ms, status, retry_count, next_attempt_at_ms, claimed_at_ms, delivered_at_ms "
            "FROM outbox WHERE decision_id=? LIMIT 1",
            (str(decision_id),),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "decision_id": row[0],
            "correlation_id": row[1],
            "action": row[2],
            "payload_json": row[3],
            "created_at_ms": int(row[4]),
            "status": row[5],
            "retry_count": int(row[6] or 0),
            "next_attempt_at_ms": int(row[7] or 0) if row[7] is not None else None,
            "claimed_at_ms": int(row[8] or 0) if row[8] is not None else None,
            "delivered_at_ms": int(row[9] or 0) if row[9] is not None else None,
        }

    def schedule_retry(self, decision_id: str, next_attempt_at_ms: int) -> None:
        assert self._conn is not None

        cur = self._conn.execute(
            "SELECT retry_count FROM outbox WHERE decision_id=?",
            (str(decision_id),),
        )
        row = cur.fetchone()
        if row is not None:
            current = int(row[0] or 0)
            if current >= MAX_RETRIES:
                self.move_to_dead_letter(decision_id)
                return

        self._conn.execute(
            "UPDATE outbox SET status='pending', next_attempt_at_ms=?, retry_count=retry_count+1, claimed_at_ms=NULL WHERE decision_id=? AND status IN ('pending','delivering')",
            (int(next_attempt_at_ms), str(decision_id)),
        )
        self._conn.commit()

    def move_to_dead_letter(self, decision_id: str) -> None:
        assert self._conn is not None
        self._conn.execute(
            "UPDATE outbox SET status='dead', claimed_at_ms=NULL WHERE decision_id=? AND status IN ('pending','delivering')",
            (str(decision_id),),
        )
        self._conn.commit()

    def has_pending(self, decision_id: str) -> bool:
        assert self._conn is not None
        cur = self._conn.execute(
            "SELECT 1 FROM outbox WHERE decision_id = ? AND status IN ('pending','delivering') LIMIT 1",
            (str(decision_id),),
        )
        return cur.fetchone() is not None

    def status(self, decision_id: str) -> str | None:
        assert self._conn is not None
        cur = self._conn.execute(
            "SELECT status FROM outbox WHERE decision_id = ? LIMIT 1",
            (str(decision_id),),
        )
        row = cur.fetchone()
        return row[0] if row else None

    def __exit__(self, exc_type, exc, tb):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def purge_delivered(self, older_than_ms: int) -> int:
        """Delete delivered outbox rows older than threshold."""
        thr = int(older_than_ms)
        with sqlite3.connect(self._path) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM outbox WHERE status='delivered' AND delivered_at_ms IS NOT NULL AND delivered_at_ms < ?", (thr,))
            conn.commit()
            return int(cur.rowcount or 0)

    def ping(self) -> bool:
        try:
            assert self._conn is not None
            self._conn.execute("SELECT 1")
            return True
        except Exception:
            return False
