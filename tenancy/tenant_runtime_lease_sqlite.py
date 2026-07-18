from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Mapping

from core.tenancy.normalization import require_tenant_id
from runtime.platform.event_store.sqlite_platform import SQLITE_ROW_FACTORY, SQLiteConnection, SQLiteRow, connect_sqlite
from tenancy.tenant_runtime_lease_store import (
    TenantRuntimeLeaseAcquireResult,
    TenantRuntimeLeaseRecord,
    TenantRuntimeLeaseStore,
    ensure_aware,
    normalize_positive_int,
    normalize_text,
    utc_now,
)


CANON_TENANT_RUNTIME_LEASE_SQLITE = True


def tenancy_runtime_lease_sqlite_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_TENANT_RUNTIME_LEASE_SQLITE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("BUSINESAIOS_TENANCY_DATA_DIR", "").strip()
    if data_dir:
        return Path(data_dir) / "tenant_runtime_leases.sqlite3"
    base = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(base) / "tenancy" / "tenant_runtime_leases.sqlite3"


class SQLiteTenantRuntimeLeaseStore(TenantRuntimeLeaseStore):
    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else tenancy_runtime_lease_sqlite_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._init_db()

    @property
    def path(self) -> Path:
        return self._path

    def acquire(
        self,
        *,
        tenant_id: str,
        run_id: str,
        owner_id: str,
        limit: int,
        ttl_seconds: int,
        labels: Mapping[str, str] | None = None,
        now: datetime | None = None,
    ) -> TenantRuntimeLeaseAcquireResult:
        tid = require_tenant_id(tenant_id)
        rid = normalize_text(run_id, field_name="run_id")
        oid = normalize_text(owner_id, field_name="owner_id")
        max_active = max(0, int(limit))
        ttl = normalize_positive_int(ttl_seconds, field_name="ttl_seconds")
        moment = ensure_aware(now or utc_now())
        encoded_labels = self._encode_labels(labels or {})
        requested_labels = json.loads(encoded_labels)
        with self._lock, self._connect(write=True) as conn:
            self._reap_expired_locked(conn, now=moment)
            row = conn.execute(
                "SELECT tenant_id, run_id, owner_id, slot_id, fencing_token, acquired_at, heartbeat_at, expires_at, labels_json "
                "FROM tenant_runtime_leases WHERE tenant_id = ? AND run_id = ?",
                (tid, rid),
            ).fetchone()
            active_runs = self._active_count_locked(conn, tenant_id=tid)
            if row is not None:
                existing = self._row_to_record(row)
                if existing.owner_id != oid:
                    return TenantRuntimeLeaseAcquireResult(False, "lease_owned_by_another_owner", tid, rid, active_runs, max_active, existing)
                if dict(existing.labels) != requested_labels:
                    return TenantRuntimeLeaseAcquireResult(False, "lease_labels_mismatch", tid, rid, active_runs, max_active, existing)
                renewed = self._renew_locked(conn, current=existing, ttl_seconds=ttl, now=moment)
                return TenantRuntimeLeaseAcquireResult(True, "already_acquired", tid, rid, active_runs, max_active, renewed)
            if max_active <= 0:
                return TenantRuntimeLeaseAcquireResult(False, "tenant_runtime_disabled", tid, rid, active_runs, max_active, None)
            if active_runs >= max_active:
                return TenantRuntimeLeaseAcquireResult(False, "tenant_runtime_capacity_exceeded", tid, rid, active_runs, max_active, None)
            token = self._next_token_locked(conn, tenant_id=tid)
            slot_id = f"tenant/{tid}/runtime/{rid}"
            conn.execute(
                "INSERT INTO tenant_runtime_leases (tenant_id, run_id, owner_id, slot_id, fencing_token, acquired_at, heartbeat_at, expires_at, labels_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (tid, rid, oid, slot_id, token, self._ts(moment), self._ts(moment), self._ts(moment, ttl_seconds=ttl), encoded_labels),
            )
            created = conn.execute(
                "SELECT tenant_id, run_id, owner_id, slot_id, fencing_token, acquired_at, heartbeat_at, expires_at, labels_json "
                "FROM tenant_runtime_leases WHERE tenant_id = ? AND run_id = ?",
                (tid, rid),
            ).fetchone()
            if created is None:
                raise RuntimeError("sqlite runtime lease insert did not persist")
            return TenantRuntimeLeaseAcquireResult(True, "acquired", tid, rid, self._active_count_locked(conn, tenant_id=tid), max_active, self._row_to_record(created))

    def renew(
        self,
        *,
        tenant_id: str,
        run_id: str,
        owner_id: str,
        ttl_seconds: int,
        now: datetime | None = None,
    ) -> TenantRuntimeLeaseRecord:
        tid = require_tenant_id(tenant_id)
        rid = normalize_text(run_id, field_name="run_id")
        oid = normalize_text(owner_id, field_name="owner_id")
        ttl = normalize_positive_int(ttl_seconds, field_name="ttl_seconds")
        moment = ensure_aware(now or utc_now())
        with self._lock, self._connect(write=True) as conn:
            self._reap_expired_locked(conn, now=moment)
            row = conn.execute(
                "SELECT tenant_id, run_id, owner_id, slot_id, fencing_token, acquired_at, heartbeat_at, expires_at, labels_json "
                "FROM tenant_runtime_leases WHERE tenant_id = ? AND run_id = ?",
                (tid, rid),
            ).fetchone()
            if row is None:
                raise KeyError(f"missing runtime lease: tenant={tid} run_id={rid}")
            current = self._row_to_record(row)
            if current.owner_id != oid:
                raise PermissionError(f"runtime lease owner mismatch: tenant={tid} run_id={rid}")
            return self._renew_locked(conn, current=current, ttl_seconds=ttl, now=moment)

    def release(self, *, tenant_id: str, run_id: str, owner_id: str) -> bool:
        tid = require_tenant_id(tenant_id)
        rid = normalize_text(run_id, field_name="run_id")
        oid = normalize_text(owner_id, field_name="owner_id")
        with self._lock, self._connect(write=True) as conn:
            row = conn.execute(
                "SELECT owner_id FROM tenant_runtime_leases WHERE tenant_id = ? AND run_id = ?",
                (tid, rid),
            ).fetchone()
            if row is None:
                return False
            if str(row[0]) != oid:
                raise PermissionError(f"runtime lease owner mismatch: tenant={tid} run_id={rid}")
            conn.execute("DELETE FROM tenant_runtime_leases WHERE tenant_id = ? AND run_id = ?", (tid, rid))
            return True

    def get(self, *, tenant_id: str, run_id: str) -> TenantRuntimeLeaseRecord | None:
        tid = require_tenant_id(tenant_id)
        rid = normalize_text(run_id, field_name="run_id")
        with self._lock, self._connect() as conn:
            self._reap_expired_locked(conn, now=utc_now())
            row = conn.execute(
                "SELECT tenant_id, run_id, owner_id, slot_id, fencing_token, acquired_at, heartbeat_at, expires_at, labels_json "
                "FROM tenant_runtime_leases WHERE tenant_id = ? AND run_id = ?",
                (tid, rid),
            ).fetchone()
            return None if row is None else self._row_to_record(row)

    def list_active(self, *, tenant_id: str, now: datetime | None = None) -> tuple[TenantRuntimeLeaseRecord, ...]:
        tid = require_tenant_id(tenant_id)
        moment = ensure_aware(now or utc_now())
        with self._lock, self._connect() as conn:
            self._reap_expired_locked(conn, now=moment)
            rows = conn.execute(
                "SELECT tenant_id, run_id, owner_id, slot_id, fencing_token, acquired_at, heartbeat_at, expires_at, labels_json "
                "FROM tenant_runtime_leases WHERE tenant_id = ? ORDER BY acquired_at, run_id",
                (tid,),
            ).fetchall()
            return tuple(self._row_to_record(row) for row in rows)

    def reap_expired(self, *, now: datetime | None = None) -> tuple[TenantRuntimeLeaseRecord, ...]:
        moment = ensure_aware(now or utc_now())
        with self._lock, self._connect(write=True) as conn:
            return self._reap_expired_locked(conn, now=moment)

    def _renew_locked(self, conn: SQLiteConnection, *, current: TenantRuntimeLeaseRecord, ttl_seconds: int, now: datetime) -> TenantRuntimeLeaseRecord:
        conn.execute(
            "UPDATE tenant_runtime_leases SET heartbeat_at = ?, expires_at = ? WHERE tenant_id = ? AND run_id = ?",
            (self._ts(now), self._ts(now, ttl_seconds=ttl_seconds), current.tenant_id, current.run_id),
        )
        row = conn.execute(
            "SELECT tenant_id, run_id, owner_id, slot_id, fencing_token, acquired_at, heartbeat_at, expires_at, labels_json "
            "FROM tenant_runtime_leases WHERE tenant_id = ? AND run_id = ?",
            (current.tenant_id, current.run_id),
        ).fetchone()
        if row is None:
            raise RuntimeError("sqlite runtime lease renew lost record")
        return self._row_to_record(row)

    def _reap_expired_locked(self, conn: SQLiteConnection, *, now: datetime) -> tuple[TenantRuntimeLeaseRecord, ...]:
        rows = conn.execute(
            "SELECT tenant_id, run_id, owner_id, slot_id, fencing_token, acquired_at, heartbeat_at, expires_at, labels_json "
            "FROM tenant_runtime_leases WHERE expires_at <= ?",
            (self._ts(now),),
        ).fetchall()
        expired = tuple(self._row_to_record(row) for row in rows)
        conn.execute("DELETE FROM tenant_runtime_leases WHERE expires_at <= ?", (self._ts(now),))
        return expired

    def _active_count_locked(self, conn: SQLiteConnection, *, tenant_id: str) -> int:
        row = conn.execute("SELECT COUNT(*) FROM tenant_runtime_leases WHERE tenant_id = ?", (tenant_id,)).fetchone()
        return int(row[0] if row is not None else 0)

    def _next_token_locked(self, conn: SQLiteConnection, *, tenant_id: str) -> int:
        row = conn.execute("SELECT next_token FROM tenant_runtime_lease_tokens WHERE tenant_id = ?", (tenant_id,)).fetchone()
        next_token = int(row[0]) + 1 if row is not None else 1
        conn.execute(
            "INSERT INTO tenant_runtime_lease_tokens (tenant_id, next_token) VALUES (?, ?) "
            "ON CONFLICT(tenant_id) DO UPDATE SET next_token = excluded.next_token",
            (tenant_id, next_token),
        )
        return next_token

    @contextmanager
    def _connect(self, *, write: bool = False) -> Iterator[SQLiteConnection]:
        conn = connect_sqlite(self._path, timeout=30.0, isolation_level=None)
        conn.row_factory = SQLITE_ROW_FACTORY
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


    def schema_version(self) -> int:
        return 1

    def read_backend_clock(self) -> datetime:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT strftime('%Y-%m-%dT%H:%M:%f+00:00','now')").fetchone()
        return ensure_aware(datetime.fromisoformat(str(row[0])))

    def _init_db(self) -> None:
        with self._connect(write=True) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS tenant_runtime_leases ("
                "tenant_id TEXT NOT NULL, "
                "run_id TEXT NOT NULL, "
                "owner_id TEXT NOT NULL, "
                "slot_id TEXT NOT NULL, "
                "fencing_token INTEGER NOT NULL, "
                "acquired_at TEXT NOT NULL, "
                "heartbeat_at TEXT NOT NULL, "
                "expires_at TEXT NOT NULL, "
                "labels_json TEXT NOT NULL, "
                "PRIMARY KEY (tenant_id, run_id)"
                ")"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS ix_tenant_runtime_leases_expires_at ON tenant_runtime_leases(expires_at)")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS tenant_runtime_lease_tokens ("
                "tenant_id TEXT PRIMARY KEY, "
                "next_token INTEGER NOT NULL"
                ")"
            )

    @staticmethod
    def _row_to_record(row: SQLiteRow) -> TenantRuntimeLeaseRecord:
        record = TenantRuntimeLeaseRecord(
            tenant_id=row["tenant_id"],
            run_id=row["run_id"],
            owner_id=row["owner_id"],
            slot_id=row["slot_id"],
            fencing_token=int(row["fencing_token"]),
            acquired_at=ensure_aware(datetime.fromisoformat(row["acquired_at"])),
            heartbeat_at=ensure_aware(datetime.fromisoformat(row["heartbeat_at"])),
            expires_at=ensure_aware(datetime.fromisoformat(row["expires_at"])),
            labels=json.loads(row["labels_json"] or "{}"),
        )
        record.validate()
        return record

    @staticmethod
    def _ts(moment: datetime, ttl_seconds: int | None = None) -> str:
        value = ensure_aware(moment)
        if ttl_seconds is not None:
            value = value + timedelta(seconds=int(ttl_seconds))
        return value.isoformat()

    @staticmethod
    def _encode_labels(labels: Mapping[str, str]) -> str:
        normalized = {
            normalize_text(k, field_name="label key"): normalize_text(v, field_name="label value")
            for k, v in dict(labels).items()
        }
        return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


__all__ = ["CANON_TENANT_RUNTIME_LEASE_SQLITE", "SQLiteTenantRuntimeLeaseStore", "tenancy_runtime_lease_sqlite_path"]
