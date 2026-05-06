from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List

import sqlite3


@dataclass(frozen=True)
class ScheduledItem:
    id: str
    user_id: str
    chat_id: int
    run_at_ms: int
    payload: Dict[str, Any]
    attempts: int


class ScheduledOutboxRepo:
    """SQLite repository for scheduled content tasks.

    This is intentionally small and uses best-effort locking suitable for SQLite.
    """

    def __init__(self, conn: sqlite3.Connection):
        self._c = conn

    def add(self, *, user_id: str, chat_id: int, run_at_ms: int, payload: Dict[str, Any]) -> str:
        now = int(time.time() * 1000)
        _id = str(uuid.uuid4())
        self._c.execute(
            "INSERT INTO scheduled_outbox(id,user_id,chat_id,run_at_ms,payload_json,status,created_at_ms) VALUES(?,?,?,?,?,'pending',?)",
            (_id, str(user_id), int(chat_id), int(run_at_ms), json.dumps(payload, ensure_ascii=False), now),
        )
        self._c.commit()
        return _id

    def lock_due(self, *, now_ms: int, limit: int = 200, lock_timeout_ms: int = 60_000) -> List[ScheduledItem]:
        # free stale locks
        self._c.execute(
            "UPDATE scheduled_outbox SET locked_at_ms=NULL WHERE status='pending' AND locked_at_ms IS NOT NULL AND locked_at_ms < ?",
            (int(now_ms) - int(lock_timeout_ms),),
        )
        self._c.commit()

        cur = self._c.execute(
            "SELECT id,user_id,chat_id,run_at_ms,payload_json,attempts FROM scheduled_outbox "
            "WHERE status='pending' AND locked_at_ms IS NULL AND run_at_ms <= ? "
            "ORDER BY run_at_ms ASC LIMIT ?",
            (int(now_ms), int(limit)),
        )
        rows = cur.fetchall()
        ids = [r[0] for r in rows]
        if not ids:
            return []

        self._c.executemany(
            "UPDATE scheduled_outbox SET locked_at_ms=? WHERE id=? AND status='pending' AND locked_at_ms IS NULL",
            [(int(now_ms), str(_id)) for _id in ids],
        )
        self._c.commit()

        out: List[ScheduledItem] = []
        for _id, user_id, chat_id, run_at_ms, payload_json, attempts in rows:
            out.append(
                ScheduledItem(
                    id=str(_id),
                    user_id=str(user_id),
                    chat_id=int(chat_id),
                    run_at_ms=int(run_at_ms),
                    payload=json.loads(payload_json),
                    attempts=int(attempts),
                )
            )
        return out

    def mark_sent(self, _id: str) -> None:
        self._c.execute("UPDATE scheduled_outbox SET status='sent', locked_at_ms=NULL WHERE id=?", (str(_id),))
        self._c.commit()

    def mark_failed(self, _id: str, *, error: str) -> None:
        self._c.execute(
            "UPDATE scheduled_outbox SET status='failed', locked_at_ms=NULL, attempts=attempts+1, last_error=? WHERE id=?",
            (str(error)[:1000], str(_id)),
        )
        self._c.commit()
