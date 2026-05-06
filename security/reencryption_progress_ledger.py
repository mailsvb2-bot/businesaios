from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CANON_REENCRYPTION_PROGRESS_LEDGER = True


@dataclass(frozen=True)
class ReencryptionProgressEvent:
    job_id: str
    event_kind: str
    secret_ref: str | None
    ok: bool
    payload: dict[str, Any]


class SQLiteReencryptionProgressLedger:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self._ensure_schema()

    def append(self, event: ReencryptionProgressEvent) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO security_reencryption_progress(job_id, event_kind, secret_ref, ok, payload_json, created_at_epoch_s) VALUES(?, ?, ?, ?, ?, ?)",
                (event.job_id, event.event_kind, event.secret_ref, 1 if event.ok else 0, json.dumps(event.payload, ensure_ascii=False, sort_keys=True), int(time.time())),
            )
            conn.commit()

    def latest_for_job(self, job_id: str, *, limit: int = 100) -> tuple[ReencryptionProgressEvent, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT job_id, event_kind, secret_ref, ok, payload_json FROM security_reencryption_progress WHERE job_id = ? ORDER BY rowid DESC LIMIT ?",
                (str(job_id), int(limit)),
            ).fetchall()
        return tuple(
            ReencryptionProgressEvent(job_id=str(r[0]), event_kind=str(r[1]), secret_ref=r[2], ok=bool(int(r[3])), payload=dict(json.loads(str(r[4] or '{}'))))
            for r in rows
        )

    def _ensure_schema(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS security_reencryption_progress (
                    job_id TEXT NOT NULL,
                    event_kind TEXT NOT NULL,
                    secret_ref TEXT NULL,
                    ok INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at_epoch_s INTEGER NOT NULL
                )
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        return conn


__all__ = [
    'CANON_REENCRYPTION_PROGRESS_LEDGER',
    'ReencryptionProgressEvent',
    'SQLiteReencryptionProgressLedger',
]
