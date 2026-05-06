from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_runtime_lease_store import (
    TenantRuntimeLeaseAcquireResult,
    TenantRuntimeLeaseRecord,
    TenantRuntimeLeaseStore,
    ensure_aware,
    normalize_positive_int,
    normalize_text,
    utc_now,
)


CANON_TENANT_RUNTIME_LEASE_POSTGRES = True
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_identifier(value: str, *, field_name: str) -> str:
    text = normalize_text(value, field_name=field_name)
    if not _IDENTIFIER_RE.fullmatch(text):
        raise ValueError(f"{field_name} must be a safe SQL identifier")
    return text


def _advisory_lock_key(*, namespace: str, tenant_id: str) -> int:
    payload = f"{namespace}:{require_tenant_id(tenant_id)}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()[:8]
    value = int.from_bytes(digest, byteorder="big", signed=False)
    if value >= 2**63:
        value -= 2**64
    return int(value)


@dataclass(frozen=True)
class PostgresTenantRuntimeLeaseStoreConfig:
    dsn: str
    leases_table: str = "tenant_runtime_leases"
    tokens_table: str = "tenant_runtime_lease_tokens"

    def validate(self) -> None:
        normalize_text(self.dsn, field_name="dsn")
        _safe_identifier(self.leases_table, field_name="leases_table")
        _safe_identifier(self.tokens_table, field_name="tokens_table")


class PostgresTenantRuntimeLeaseStore(TenantRuntimeLeaseStore):
    def __init__(self, config: PostgresTenantRuntimeLeaseStoreConfig) -> None:
        config.validate()
        self._config = config
        try:
            import psycopg
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgresTenantRuntimeLeaseStore") from exc
        self._psycopg = psycopg
        self._init_db()

    def acquire(self, *, tenant_id: str, run_id: str, owner_id: str, limit: int, ttl_seconds: int, labels: Mapping[str, str] | None = None, now: datetime | None = None) -> TenantRuntimeLeaseAcquireResult:
        tid = require_tenant_id(tenant_id)
        rid = normalize_text(run_id, field_name="run_id")
        oid = normalize_text(owner_id, field_name="owner_id")
        max_active = max(0, int(limit))
        ttl = normalize_positive_int(ttl_seconds, field_name="ttl_seconds")
        moment = ensure_aware(now or utc_now())
        normalized_labels = {normalize_text(k, field_name="label key"): normalize_text(v, field_name="label value") for k, v in dict(labels or {}).items()}
        with self._connect() as conn, conn.cursor() as cur:
            self._tenant_lock(cur, tenant_id=tid)
            self._reap_expired_locked(cur, now=moment)
            cur.execute(
                f"SELECT tenant_id, run_id, owner_id, slot_id, fencing_token, acquired_at, heartbeat_at, expires_at, labels_json FROM {self._config.leases_table} WHERE tenant_id = %s AND run_id = %s FOR UPDATE",
                (tid, rid),
            )
            row = cur.fetchone()
            active_runs = self._active_count_locked(cur, tenant_id=tid)
            if row is not None:
                existing = self._row_to_record(row)
                if existing.owner_id != oid:
                    conn.commit()
                    return TenantRuntimeLeaseAcquireResult(False, "lease_owned_by_another_owner", tid, rid, active_runs, max_active, existing)
                if dict(existing.labels) != normalized_labels:
                    conn.commit()
                    return TenantRuntimeLeaseAcquireResult(False, "lease_labels_mismatch", tid, rid, active_runs, max_active, existing)
                renewed = self._renew_locked(cur, current=existing, ttl_seconds=ttl, now=moment)
                conn.commit()
                return TenantRuntimeLeaseAcquireResult(True, "already_acquired", tid, rid, active_runs, max_active, renewed)
            if max_active <= 0:
                conn.commit()
                return TenantRuntimeLeaseAcquireResult(False, "tenant_runtime_disabled", tid, rid, active_runs, max_active, None)
            if active_runs >= max_active:
                conn.commit()
                return TenantRuntimeLeaseAcquireResult(False, "tenant_runtime_capacity_exceeded", tid, rid, active_runs, max_active, None)
            token = self._next_token_locked(cur, tenant_id=tid)
            cur.execute(
                f"INSERT INTO {self._config.leases_table} (tenant_id, run_id, owner_id, slot_id, fencing_token, acquired_at, heartbeat_at, expires_at, labels_json) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (tid, rid, oid, f"tenant/{tid}/runtime/{rid}", token, moment, moment, moment + timedelta(seconds=ttl), json.dumps(normalized_labels, sort_keys=True, separators=(",", ":"))),
            )
            cur.execute(
                f"SELECT tenant_id, run_id, owner_id, slot_id, fencing_token, acquired_at, heartbeat_at, expires_at, labels_json FROM {self._config.leases_table} WHERE tenant_id = %s AND run_id = %s",
                (tid, rid),
            )
            created = cur.fetchone()
            if created is None:
                raise RuntimeError("postgres runtime lease insert did not persist")
            conn.commit()
            return TenantRuntimeLeaseAcquireResult(True, "acquired", tid, rid, active_runs + 1, max_active, self._row_to_record(created))

    def renew(self, *, tenant_id: str, run_id: str, owner_id: str, ttl_seconds: int, now: datetime | None = None) -> TenantRuntimeLeaseRecord:
        tid = require_tenant_id(tenant_id)
        rid = normalize_text(run_id, field_name="run_id")
        oid = normalize_text(owner_id, field_name="owner_id")
        ttl = normalize_positive_int(ttl_seconds, field_name="ttl_seconds")
        moment = ensure_aware(now or utc_now())
        with self._connect() as conn, conn.cursor() as cur:
            self._tenant_lock(cur, tenant_id=tid)
            self._reap_expired_locked(cur, now=moment)
            cur.execute(
                f"SELECT tenant_id, run_id, owner_id, slot_id, fencing_token, acquired_at, heartbeat_at, expires_at, labels_json FROM {self._config.leases_table} WHERE tenant_id = %s AND run_id = %s FOR UPDATE",
                (tid, rid),
            )
            row = cur.fetchone()
            if row is None:
                raise KeyError(f"missing runtime lease: tenant={tid} run_id={rid}")
            current = self._row_to_record(row)
            if current.owner_id != oid:
                raise PermissionError(f"runtime lease owner mismatch: tenant={tid} run_id={rid}")
            if current.expires_at <= moment:
                raise KeyError(f"expired runtime lease: tenant={tid} run_id={rid}")
            renewed = self._renew_locked(cur, current=current, ttl_seconds=ttl, now=moment)
            conn.commit()
            return renewed

    def release(self, *, tenant_id: str, run_id: str, owner_id: str) -> bool:
        tid = require_tenant_id(tenant_id)
        rid = normalize_text(run_id, field_name="run_id")
        oid = normalize_text(owner_id, field_name="owner_id")
        with self._connect() as conn, conn.cursor() as cur:
            self._tenant_lock(cur, tenant_id=tid)
            self._reap_expired_locked(cur, now=utc_now())
            cur.execute(f"SELECT owner_id FROM {self._config.leases_table} WHERE tenant_id = %s AND run_id = %s FOR UPDATE", (tid, rid))
            row = cur.fetchone()
            if row is None:
                conn.commit()
                return False
            if str(row[0]) != oid:
                raise PermissionError(f"runtime lease owner mismatch: tenant={tid} run_id={rid}")
            cur.execute(f"DELETE FROM {self._config.leases_table} WHERE tenant_id = %s AND run_id = %s", (tid, rid))
            conn.commit()
            return True

    def get(self, *, tenant_id: str, run_id: str) -> TenantRuntimeLeaseRecord | None:
        tid = require_tenant_id(tenant_id)
        rid = normalize_text(run_id, field_name="run_id")
        with self._connect() as conn, conn.cursor() as cur:
            self._tenant_lock(cur, tenant_id=tid)
            self._reap_expired_locked(cur, now=utc_now())
            cur.execute(
                f"SELECT tenant_id, run_id, owner_id, slot_id, fencing_token, acquired_at, heartbeat_at, expires_at, labels_json FROM {self._config.leases_table} WHERE tenant_id = %s AND run_id = %s",
                (tid, rid),
            )
            row = cur.fetchone()
            conn.commit()
            return None if row is None else self._row_to_record(row)

    def list_active(self, *, tenant_id: str, now: datetime | None = None) -> tuple[TenantRuntimeLeaseRecord, ...]:
        tid = require_tenant_id(tenant_id)
        moment = ensure_aware(now or utc_now())
        with self._connect() as conn, conn.cursor() as cur:
            self._tenant_lock(cur, tenant_id=tid)
            self._reap_expired_locked(cur, now=moment)
            cur.execute(
                f"SELECT tenant_id, run_id, owner_id, slot_id, fencing_token, acquired_at, heartbeat_at, expires_at, labels_json FROM {self._config.leases_table} WHERE tenant_id = %s ORDER BY acquired_at, run_id",
                (tid,),
            )
            rows = cur.fetchall()
            conn.commit()
            return tuple(self._row_to_record(row) for row in rows)

    def reap_expired(self, *, now: datetime | None = None) -> tuple[TenantRuntimeLeaseRecord, ...]:
        moment = ensure_aware(now or utc_now())
        with self._connect() as conn, conn.cursor() as cur:
            expired = self._reap_expired_locked(cur, now=moment)
            conn.commit()
            return expired

    def _renew_locked(self, cur: Any, *, current: TenantRuntimeLeaseRecord, ttl_seconds: int, now: datetime) -> TenantRuntimeLeaseRecord:
        cur.execute(
            f"UPDATE {self._config.leases_table} SET heartbeat_at = %s, expires_at = %s WHERE tenant_id = %s AND run_id = %s",
            (now, now + timedelta(seconds=ttl_seconds), current.tenant_id, current.run_id),
        )
        cur.execute(
            f"SELECT tenant_id, run_id, owner_id, slot_id, fencing_token, acquired_at, heartbeat_at, expires_at, labels_json FROM {self._config.leases_table} WHERE tenant_id = %s AND run_id = %s",
            (current.tenant_id, current.run_id),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("postgres runtime lease renew lost record")
        return self._row_to_record(row)

    def _reap_expired_locked(self, cur: Any, *, now: datetime) -> tuple[TenantRuntimeLeaseRecord, ...]:
        cur.execute(
            f"SELECT tenant_id, run_id, owner_id, slot_id, fencing_token, acquired_at, heartbeat_at, expires_at, labels_json FROM {self._config.leases_table} WHERE expires_at <= %s",
            (now,),
        )
        rows = cur.fetchall()
        cur.execute(f"DELETE FROM {self._config.leases_table} WHERE expires_at <= %s", (now,))
        return tuple(self._row_to_record(row) for row in rows)

    def _active_count_locked(self, cur: Any, *, tenant_id: str) -> int:
        cur.execute(f"SELECT COUNT(*) FROM {self._config.leases_table} WHERE tenant_id = %s", (tenant_id,))
        row = cur.fetchone()
        return int(row[0] if row is not None else 0)

    def _next_token_locked(self, cur: Any, *, tenant_id: str) -> int:
        cur.execute(f"SELECT next_token FROM {self._config.tokens_table} WHERE tenant_id = %s FOR UPDATE", (tenant_id,))
        row = cur.fetchone()
        next_token = int(row[0]) + 1 if row is not None else 1
        cur.execute(
            f"INSERT INTO {self._config.tokens_table} (tenant_id, next_token) VALUES (%s, %s) ON CONFLICT (tenant_id) DO UPDATE SET next_token = EXCLUDED.next_token",
            (tenant_id, next_token),
        )
        return next_token

    @staticmethod
    def _tenant_lock(cur: Any, *, tenant_id: str) -> None:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (_advisory_lock_key(namespace="tenant-runtime-lease", tenant_id=tenant_id),))

    def _init_db(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {self._config.leases_table} ("
                "tenant_id TEXT NOT NULL, "
                "run_id TEXT NOT NULL, "
                "owner_id TEXT NOT NULL, "
                "slot_id TEXT NOT NULL, "
                "fencing_token BIGINT NOT NULL, "
                "acquired_at TIMESTAMPTZ NOT NULL, "
                "heartbeat_at TIMESTAMPTZ NOT NULL, "
                "expires_at TIMESTAMPTZ NOT NULL, "
                "labels_json JSONB NOT NULL, "
                "PRIMARY KEY (tenant_id, run_id)"
                ")"
            )
            cur.execute(f"CREATE INDEX IF NOT EXISTS ix_{self._config.leases_table}_expires_at ON {self._config.leases_table}(expires_at)")
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {self._config.tokens_table} (tenant_id TEXT PRIMARY KEY, next_token BIGINT NOT NULL)"
            )
            conn.commit()

    def _connect(self):
        return self._psycopg.connect(self._config.dsn)

    @staticmethod
    def _row_to_record(row: Any) -> TenantRuntimeLeaseRecord:
        labels = row[8] if len(row) > 8 else {}
        if isinstance(labels, str):
            labels = json.loads(labels)
        record = TenantRuntimeLeaseRecord(
            tenant_id=row[0],
            run_id=row[1],
            owner_id=row[2],
            slot_id=row[3],
            fencing_token=int(row[4]),
            acquired_at=ensure_aware(row[5]),
            heartbeat_at=ensure_aware(row[6]),
            expires_at=ensure_aware(row[7]),
            labels=dict(labels or {}),
        )
        record.validate()
        return record


__all__ = ["CANON_TENANT_RUNTIME_LEASE_POSTGRES", "PostgresTenantRuntimeLeaseStore", "PostgresTenantRuntimeLeaseStoreConfig"]
