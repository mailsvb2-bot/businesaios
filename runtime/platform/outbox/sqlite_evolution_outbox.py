from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from runtime.platform.config.env_flags import env_int, env_path, env_str
from runtime.platform.outbox.sqlite_pragmas import configure_sqlite, is_prod_env


@dataclass(frozen=True)
class EvolutionJob:
    job_id: str
    job_kind: str
    payload: dict[str, Any]
    status: str
    created_ms: int
    updated_ms: int
    error: str | None = None


DDL = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS evolution_jobs (
  job_id TEXT PRIMARY KEY,
  job_kind TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_ms INTEGER NOT NULL,
  updated_ms INTEGER NOT NULL,
  error TEXT
);
CREATE INDEX IF NOT EXISTS idx_evolution_jobs_status_updated ON evolution_jobs(status, updated_ms);
"""


def _now_ms() -> int:
    return int(time.time() * 1000)


class SqliteEvolutionOutbox:
    def __init__(self, path: str):
        self._path = str(path)

    @staticmethod
    def default_path_from_env() -> str:
        p = env_str("EVOLUTION_DB_PATH", "").strip()
        if not p:
            data_dir = str(env_path("DATA_DIR", os.path.join("runtime", "entrypoints", "data")))
            p = os.path.join(data_dir, "evolution.db")
        return p

    def _connect(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        conn = sqlite3.connect(self._path, timeout=5.0, check_same_thread=False)
        configure_sqlite(conn, prod=is_prod_env())
        conn.executescript(DDL)
        conn.commit()
        return conn

    def enqueue(self, *, job_kind: str, payload: dict[str, Any] | None = None, job_id: str | None = None) -> str:
        jid = str(job_id or uuid.uuid4())
        now = _now_ms()
        pl = dict(payload or {})
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO evolution_jobs(job_id, job_kind, payload_json, status, created_ms, updated_ms, error) "
                "VALUES(?,?,?,?,?,?,?)",
                (jid, str(job_kind), json.dumps(pl, ensure_ascii=False, sort_keys=True), "pending", now, now, None),
            )
            db.commit()
        return jid

    def list_pending(self, *, limit: int = 10) -> list[EvolutionJob]:
        lim = max(1, min(100, int(limit)))
        with self._connect() as db:
            rows = db.execute(
                "SELECT job_id, job_kind, payload_json, status, created_ms, updated_ms, error "
                "FROM evolution_jobs WHERE status='pending' ORDER BY updated_ms ASC LIMIT ?",
                (lim,),
            ).fetchall()
        out: list[EvolutionJob] = []
        for r in rows:
            try:
                payload = json.loads(r[2]) if r[2] else {}
            except Exception:
                payload = {}
            out.append(
                EvolutionJob(
                    job_id=str(r[0]),
                    job_kind=str(r[1]),
                    payload=payload if isinstance(payload, dict) else {"value": payload},
                    status=str(r[3]),
                    created_ms=int(r[4]),
                    updated_ms=int(r[5]),
                    error=(str(r[6]) if r[6] is not None else None),
                )
            )
        return out

    def mark_done(self, job_id: str) -> None:
        now = _now_ms()
        with self._connect() as db:
            db.execute("UPDATE evolution_jobs SET status='done', updated_ms=?, error=NULL WHERE job_id=?", (now, str(job_id)))
            db.commit()

    def mark_failed(self, job_id: str, error: str | None = None) -> None:
        now = _now_ms()
        with self._connect() as db:
            db.execute(
                "UPDATE evolution_jobs SET status='failed', updated_ms=?, error=? WHERE job_id=?",
                (now, (str(error)[:500] if error else None), str(job_id)),
            )
            db.commit()


    def get_status(self, job_id: str) -> str | None:
        with self._connect() as db:
            row = db.execute("SELECT status FROM evolution_jobs WHERE job_id=?", (str(job_id),)).fetchone()
        return str(row[0]) if row else None

    def count_pending(self) -> int:
        with self._connect() as db:
            row = db.execute("SELECT COUNT(1) FROM evolution_jobs WHERE status='pending'").fetchone()
            return int(row[0] if row else 0)

    def ping(self) -> bool:
        try:
            with self._connect() as db:
                db.execute("SELECT 1")
            return True
        except Exception:
            return False
