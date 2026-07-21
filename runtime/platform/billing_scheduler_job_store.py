from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from math import isfinite
from pathlib import Path
from typing import Any

from core.tenancy.normalization import require_tenant_id

CANON_PLATFORM_BILLING_SCHEDULER_JOB_STORE = True
SCHEMA_VERSION = 1


def _require_text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def canonical_json_snapshot(value: Any, *, name: str = "metadata") -> Any:
    """Return the one canonical JSON-safe snapshot used by billing job stores."""

    if value is None or isinstance(value, (str, bool)):
        return value
    if type(value) is int:
        return value
    if type(value) is float:
        if not isfinite(value):
            raise ValueError(f"{name} must contain finite numbers")
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = _require_text(f"{name} key", raw_key)
            if key in result:
                raise ValueError(f"duplicate {name} key: {key}")
            result[key] = canonical_json_snapshot(raw_value, name=f"{name}[{key}]")
        return result
    if isinstance(value, (list, tuple)):
        return [canonical_json_snapshot(item, name=f"{name} item") for item in value]
    raise ValueError(f"{name} must contain JSON-compatible values")


def _normalized_run(run: Any) -> Any:
    normalizer = getattr(run, "normalized_copy", None)
    normalized = normalizer() if callable(normalizer) else run
    validator = getattr(normalized, "validate", None)
    if not callable(validator):
        raise ValueError("run must provide validate()")
    validator()
    return deepcopy(normalized)


class PlatformSqliteBillingJobRunStore:
    def __init__(self, *, sqlite_path: str, run_cls: type) -> None:
        self._path = str(sqlite_path).strip()
        self._run_cls = run_cls
        if not self._path:
            raise ValueError("sqlite_path is required")
        if not isinstance(run_cls, type):
            raise ValueError("run_cls must be a type")
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path, timeout=30.0)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS billing_schema_version "
                "(component TEXT PRIMARY KEY, version INTEGER NOT NULL)"
            )
            row = conn.execute(
                "SELECT version FROM billing_schema_version WHERE component = ?",
                ("job_runs",),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO billing_schema_version(component, version) VALUES (?, ?)",
                    ("job_runs", SCHEMA_VERSION),
                )
            elif type(row[0]) is not int or row[0] != SCHEMA_VERSION:
                raise RuntimeError("unsupported job_runs schema version")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS billing_job_runs (
                    tenant_id TEXT NOT NULL,
                    job_name TEXT NOT NULL,
                    run_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, job_name, run_key)
                )
                """
            )

    def save(self, run: Any) -> Any:
        normalized = _normalized_run(run)
        tid = require_tenant_id(normalized.tenant_id)
        job_name = _require_text("job_name", normalized.job_name)
        run_key = _require_text("run_key", normalized.run_key)
        payload = {
            "tenant_id": tid,
            "job_name": job_name,
            "run_key": run_key,
            "started_at": normalized.started_at.isoformat(),
            "finished_at": None if normalized.finished_at is None else normalized.finished_at.isoformat(),
            "metadata": canonical_json_snapshot(normalized.metadata),
        }
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO billing_job_runs"
                "(tenant_id, job_name, run_key, payload_json) VALUES (?, ?, ?, ?)",
                (tid, job_name, run_key, payload_json),
            )
            row = conn.execute(
                "SELECT payload_json FROM billing_job_runs "
                "WHERE tenant_id = ? AND job_name = ? AND run_key = ?",
                (tid, job_name, run_key),
            ).fetchone()
            if row is None:
                raise RuntimeError("billing job run insert was not persisted")
            existing = self._decode(row[0])
            if existing != normalized:
                raise ValueError("billing job run collision")
            return deepcopy(existing)

    def get(self, *, tenant_id: str, job_name: str, run_key: str) -> Any | None:
        if not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a string")
        tid = require_tenant_id(tenant_id)
        normalized_job = _require_text("job_name", job_name)
        normalized_key = _require_text("run_key", run_key)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM billing_job_runs "
                "WHERE tenant_id = ? AND job_name = ? AND run_key = ?",
                (tid, normalized_job, normalized_key),
            ).fetchone()
        return None if row is None else deepcopy(self._decode(row[0]))

    def _decode(self, payload_json: str) -> Any:
        if not isinstance(payload_json, str):
            raise ValueError("payload_json must be a string")
        payload = json.loads(payload_json)
        if not isinstance(payload, Mapping):
            raise ValueError("billing job payload must be a mapping")
        normalized_payload = dict(payload)
        started_at = normalized_payload.get("started_at")
        if not isinstance(started_at, str):
            raise ValueError("started_at must be an ISO datetime string")
        normalized_payload["started_at"] = datetime.fromisoformat(started_at)
        finished_at = normalized_payload.get("finished_at")
        if finished_at is not None:
            if not isinstance(finished_at, str):
                raise ValueError("finished_at must be an ISO datetime string")
            normalized_payload["finished_at"] = datetime.fromisoformat(finished_at)
        normalized_payload["metadata"] = canonical_json_snapshot(
            normalized_payload.get("metadata", {}),
            name="metadata",
        )
        return _normalized_run(self._run_cls(**normalized_payload))


__all__ = [
    "CANON_PLATFORM_BILLING_SCHEDULER_JOB_STORE",
    "PlatformSqliteBillingJobRunStore",
    "SCHEMA_VERSION",
    "canonical_json_snapshot",
]
