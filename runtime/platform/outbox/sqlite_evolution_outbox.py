from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Any

from runtime.platform.config.env_flags import env_path, env_str
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


def _canonical_payload_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        dict(payload or {}),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _canonical_stored_payload(raw: object) -> str:
    try:
        decoded = json.loads(str(raw or "{}"))
        if not isinstance(decoded, dict):
            return str(raw or "")
        return _canonical_payload_json(decoded)
    except (TypeError, ValueError, json.JSONDecodeError):
        return str(raw or "")


class SqliteEvolutionOutbox:
    def __init__(self, path: str):
        self._path = str(path)

    @staticmethod
    def default_path_from_env() -> str:
        path = env_str("EVOLUTION_DB_PATH", "").strip()
        if not path:
            data_dir = str(
                env_path(
                    "DATA_DIR",
                    os.path.join("runtime", "entrypoints", "data"),
                )
            )
            path = os.path.join(data_dir, "evolution.db")
        return path

    def _connect(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        connection = sqlite3.connect(
            self._path,
            timeout=5.0,
            check_same_thread=False,
        )
        configure_sqlite(connection, prod=is_prod_env())
        connection.executescript(DDL)
        connection.commit()
        return connection

    def enqueue(
        self,
        *,
        job_kind: str,
        payload: dict[str, Any] | None = None,
        job_id: str | None = None,
    ) -> str:
        job = str(job_id or uuid.uuid4()).strip()
        kind = str(job_kind or "").strip()
        if not job:
            raise ValueError("job_id is required")
        if not kind:
            raise ValueError("job_kind is required")
        payload_json = _canonical_payload_json(dict(payload or {}))
        now = _now_ms()

        with self._connect() as database:
            database.execute(
                "INSERT OR IGNORE INTO evolution_jobs("
                "job_id, job_kind, payload_json, status, created_ms, updated_ms, error"
                ") VALUES(?,?,?,?,?,?,?)",
                (job, kind, payload_json, "pending", now, now, None),
            )
            row = database.execute(
                "SELECT job_kind, payload_json, status "
                "FROM evolution_jobs WHERE job_id=?",
                (job,),
            ).fetchone()
            if row is None:
                raise RuntimeError(f"EVOLUTION_JOB_PERSISTENCE_FAILED:{job}")
            existing_kind = str(row[0] or "")
            existing_payload = _canonical_stored_payload(row[1])
            if existing_kind != kind or existing_payload != payload_json:
                raise RuntimeError(f"EVOLUTION_JOB_ID_CONFLICT:{job}")
            # INSERT OR IGNORE plus post-read validation closes the concurrent
            # enqueue race while preserving pending/done/failed state.
            database.commit()
        return job

    def list_pending(self, *, limit: int = 10) -> list[EvolutionJob]:
        bounded_limit = max(1, min(100, int(limit)))
        with self._connect() as database:
            rows = database.execute(
                "SELECT job_id, job_kind, payload_json, status, created_ms, "
                "updated_ms, error FROM evolution_jobs WHERE status='pending' "
                "ORDER BY updated_ms ASC LIMIT ?",
                (bounded_limit,),
            ).fetchall()
        output: list[EvolutionJob] = []
        for row in rows:
            try:
                payload = json.loads(row[2]) if row[2] else {}
            except Exception:
                payload = {}
            output.append(
                EvolutionJob(
                    job_id=str(row[0]),
                    job_kind=str(row[1]),
                    payload=(
                        payload
                        if isinstance(payload, dict)
                        else {"value": payload}
                    ),
                    status=str(row[3]),
                    created_ms=int(row[4]),
                    updated_ms=int(row[5]),
                    error=(str(row[6]) if row[6] is not None else None),
                )
            )
        return output

    def mark_done(self, job_id: str) -> None:
        now = _now_ms()
        with self._connect() as database:
            database.execute(
                "UPDATE evolution_jobs SET status='done', updated_ms=?, "
                "error=NULL WHERE job_id=?",
                (now, str(job_id)),
            )
            database.commit()

    def mark_failed(self, job_id: str, error: str | None = None) -> None:
        now = _now_ms()
        with self._connect() as database:
            database.execute(
                "UPDATE evolution_jobs SET status='failed', updated_ms=?, "
                "error=? WHERE job_id=?",
                (now, (str(error)[:500] if error else None), str(job_id)),
            )
            database.commit()

    def get_status(self, job_id: str) -> str | None:
        with self._connect() as database:
            row = database.execute(
                "SELECT status FROM evolution_jobs WHERE job_id=?",
                (str(job_id),),
            ).fetchone()
        return str(row[0]) if row else None

    def count_pending(self) -> int:
        with self._connect() as database:
            row = database.execute(
                "SELECT COUNT(1) FROM evolution_jobs WHERE status='pending'"
            ).fetchone()
            return int(row[0] if row else 0)

    def ping(self) -> bool:
        try:
            with self._connect() as database:
                database.execute("SELECT 1")
            return True
        except Exception:
            return False
