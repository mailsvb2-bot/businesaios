"""Durable Telegram ingress inbox, stored in the canonical delivery-state SQLite DB.

Updates are committed before the Bot API cursor can advance. Pending updates
survive restarts, and only confirmed canonical outcomes become completed.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from typing import Any

from runtime.platform.delivery_state import _ensure_db, _get_db_path, _open_connection

DEFAULT_MAX_ATTEMPTS = 12
MAX_RETRY_DELAY_S = 300
_TERMINAL_PREFIXES = (
    "DECISION_BLOCKED:",
    "idempotency_resolution:rejected_terminal_failed",
    "idempotency_resolution:rejected_scope_mismatch",
)
_TRANSIENT_CODES = frozenset({"DECISION_BLOCKED:action_safety_gate_error"})
_SAFE_CODE = re.compile(r"[A-Za-z0-9_.:-]{1,120}")


def failure_code(exc: BaseException) -> str:
    value = str(exc).strip()
    if value.startswith((*_TERMINAL_PREFIXES, "telegram_update_")) and _SAFE_CODE.fullmatch(value):
        return value
    return type(exc).__name__


def is_terminal_failure(exc: BaseException) -> bool:
    code = failure_code(exc)
    return code.startswith(_TERMINAL_PREFIXES) and code not in _TRANSIENT_CODES





class TelegramTerminalOutcome(RuntimeError):
    """A verified update has an ambiguous terminal effect outcome.

    Never automatically retry: the external effect might already have occurred.
    Keep the payload in dead-letter for verified reconciliation/operator review.
    """


class TelegramInbox:
    def __init__(self, token: str) -> None:
        # Never persist an API credential.
        self.scope = hashlib.sha256(token.encode("utf-8")).hexdigest()
        path = _get_db_path()
        _ensure_db(path)
        self.path = path
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS telegram_ingress_inbox (
                bot_scope TEXT NOT NULL,
                update_id INTEGER NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                retry_at REAL NOT NULL DEFAULT 0,
                last_error TEXT,
                PRIMARY KEY (bot_scope, update_id)
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS telegram_ingress_cursor (
                bot_scope TEXT PRIMARY KEY,
                next_offset INTEGER NOT NULL
            )""")

    def _db(self) -> sqlite3.Connection:
        return _open_connection(self.path)

    def cursor(self) -> int | None:
        with self._db() as db:
            row = db.execute("SELECT next_offset FROM telegram_ingress_cursor WHERE bot_scope=?",
                             (self.scope,)).fetchone()
            return int(row[0]) if row else None

    def stage(self, updates: list[dict[str, Any]]) -> int | None:
        """Atomically persist the complete poll batch and its next cursor."""
        ids: list[int] = []
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            for update in updates:
                if not isinstance(update, dict) or type(update.get("update_id")) is not int:
                    raise ValueError("telegram_update_id_required")
                uid = update["update_id"]
                if uid < 0:
                    raise ValueError("telegram_update_id_invalid")
                serialized = json.dumps(update, ensure_ascii=False, separators=(",", ":"))
                db.execute("""INSERT INTO telegram_ingress_inbox(bot_scope,update_id,payload)
                              VALUES(?,?,?) ON CONFLICT(bot_scope,update_id) DO NOTHING""",
                           (self.scope, uid, serialized))
                ids.append(uid)
            if ids:
                next_offset = max(ids) + 1
                db.execute("""INSERT INTO telegram_ingress_cursor(bot_scope,next_offset)
                              VALUES(?,?) ON CONFLICT(bot_scope) DO UPDATE SET
                              next_offset=MAX(next_offset,excluded.next_offset)""",
                           (self.scope, next_offset))
        return self.cursor()

    def due(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute("""SELECT payload FROM telegram_ingress_inbox
                                 WHERE bot_scope=? AND status='pending' AND retry_at<=?
                                 ORDER BY update_id LIMIT ?""",
                              (self.scope, time.time(), max(1, min(limit, 1000)))).fetchall()
        return [json.loads(row[0]) for row in rows]

    def complete(self, update_id: int) -> None:
        with self._db() as db:
            db.execute("""UPDATE telegram_ingress_inbox SET status='completed',last_error=NULL
                          WHERE bot_scope=? AND update_id=?""", (self.scope, update_id))

    @staticmethod
    def retry_horizon_s(max_attempts: int = DEFAULT_MAX_ATTEMPTS, max_delay: int = MAX_RETRY_DELAY_S) -> int:
        return sum(min(max_delay, 2 ** min(n - 1, 12))
                   for n in range(1, max(1, int(max_attempts))))

    def failed(self, update_id: int, exc: Exception, *, max_delay: int = MAX_RETRY_DELAY_S,
               max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> str:
        max_attempts, max_delay = max(1, int(max_attempts)), max(1, int(max_delay))
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""SELECT attempts FROM telegram_ingress_inbox
                                WHERE bot_scope=? AND update_id=? AND status='pending'""",
                             (self.scope, update_id)).fetchone()
            if row is None:
                raise RuntimeError("telegram_inbox_missing_pending_update")
            attempts = int(row[0]) + 1
            status = ("dead_letter" if isinstance(exc, TelegramTerminalOutcome)
                      or is_terminal_failure(exc) or attempts >= max_attempts else "pending")
            delay = min(max_delay, 2 ** min(attempts - 1, 12))
            db.execute("""UPDATE telegram_ingress_inbox
                          SET status=?,attempts=?,retry_at=?,last_error=?
                          WHERE bot_scope=? AND update_id=? AND status='pending'""",
                       (status, attempts, 0 if status == "dead_letter" else time.time() + delay,
                        failure_code(exc), self.scope, update_id))
        return status

    def dead_letter_count(self) -> int:
        with self._db() as db:
            return int(db.execute("""SELECT COUNT(*) FROM telegram_ingress_inbox
                                     WHERE bot_scope=? AND status='dead_letter'""",
                                  (self.scope,)).fetchone()[0])

    def backlog_counts(self) -> dict[str, int]:
        with self._db() as db:
            rows = db.execute("""SELECT status,COUNT(*) FROM telegram_ingress_inbox
                                 WHERE bot_scope=? AND status IN ('pending','dead_letter')
                                 GROUP BY status""", (self.scope,)).fetchall()
        counts = {"pending": 0, "dead_letter": 0}
        counts.update({str(status): int(count) for status, count in rows if status in counts})
        return counts

    def requeue_dead_letter(self, update_id: int) -> bool:
        with self._db() as db:
            result = db.execute("""UPDATE telegram_ingress_inbox
                                   SET status='pending',attempts=0,retry_at=0,last_error=NULL
                                   WHERE bot_scope=? AND update_id=? AND status='dead_letter'""",
                                (self.scope, update_id))
        return result.rowcount > 0

    def pending_count(self) -> int:
        with self._db() as db:
            return int(db.execute("""SELECT COUNT(*) FROM telegram_ingress_inbox
                                     WHERE bot_scope=? AND status='pending'""",
                                  (self.scope,)).fetchone()[0])
