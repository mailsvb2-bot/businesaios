from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_migration_lock_backend import (
    TenantMigrationLockBackend,
    TenantMigrationLockRecord,
    ensure_aware,
    utc_now,
)


CANON_TENANT_MIGRATION_LOCK_POSTGRES = True
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_identifier(value: str, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
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
class PostgresTenantMigrationLockBackendConfig:
    dsn: str
    table_name: str = "tenant_migration_locks"
    token_table: str = "tenant_migration_lock_tokens"

    def validate(self) -> None:
        if not str(self.dsn or "").strip():
            raise ValueError("dsn is required")
        _safe_identifier(self.table_name, field_name="table_name")
        _safe_identifier(self.token_table, field_name="token_table")


class PostgresTenantMigrationLockBackend(TenantMigrationLockBackend):
    def __init__(self, config: PostgresTenantMigrationLockBackendConfig) -> None:
        config.validate()
        self._config = config
        try:
            import psycopg
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgresTenantMigrationLockBackend") from exc
        self._psycopg = psycopg
        self._init_db()

    def acquire(self, *, tenant_id: str, operation_id: str, owner_id: str, ttl_seconds: int, now: datetime | None = None) -> TenantMigrationLockRecord | None:
        tid = require_tenant_id(tenant_id)
        oid = str(operation_id or "").strip()
        owner = str(owner_id or "").strip()
        ttl = int(ttl_seconds)
        if not oid or not owner:
            raise ValueError("operation_id and owner_id are required")
        if ttl <= 0:
            raise ValueError("ttl_seconds must be > 0")
        moment = ensure_aware(now or utc_now())
        with self._connect() as conn, conn.cursor() as cur:
            self._tenant_lock(cur, tenant_id=tid)
            self._reap_expired_locked(cur, now=moment, tenant_id=tid)
            cur.execute(
                f"SELECT tenant_id, operation_id, owner_id, fencing_token, acquired_at, expires_at FROM {self._config.table_name} WHERE tenant_id = %s FOR UPDATE",
                (tid,),
            )
            row = cur.fetchone()
            if row is not None:
                existing = TenantMigrationLockRecord(row[0], row[1], row[2], int(row[3]), row[4], row[5])
                existing.validate()
                if existing.operation_id == oid and existing.owner_id == owner:
                    expires_at = moment + timedelta(seconds=ttl)
                    cur.execute(f"UPDATE {self._config.table_name} SET expires_at = %s WHERE tenant_id = %s", (expires_at, tid))
                    conn.commit()
                    return TenantMigrationLockRecord(existing.tenant_id, existing.operation_id, existing.owner_id, existing.fencing_token, existing.acquired_at, expires_at)
                conn.commit()
                return None
            token = self._next_token_locked(cur, tenant_id=tid)
            expires_at = moment + timedelta(seconds=ttl)
            cur.execute(
                f"INSERT INTO {self._config.table_name} (tenant_id, operation_id, owner_id, fencing_token, acquired_at, expires_at) VALUES (%s, %s, %s, %s, %s, %s)",
                (tid, oid, owner, token, moment, expires_at),
            )
            conn.commit()
            lock = TenantMigrationLockRecord(tid, oid, owner, int(token), moment, expires_at)
            lock.validate()
            return lock

    def renew(self, *, tenant_id: str, operation_id: str, owner_id: str, ttl_seconds: int, now: datetime | None = None) -> TenantMigrationLockRecord:
        tid = require_tenant_id(tenant_id)
        oid = str(operation_id or "").strip()
        owner = str(owner_id or "").strip()
        ttl = int(ttl_seconds)
        if not oid or not owner:
            raise ValueError("operation_id and owner_id are required")
        if ttl <= 0:
            raise ValueError("ttl_seconds must be > 0")
        moment = ensure_aware(now or utc_now())
        with self._connect() as conn, conn.cursor() as cur:
            self._tenant_lock(cur, tenant_id=tid)
            self._reap_expired_locked(cur, now=moment, tenant_id=tid)
            cur.execute(
                f"SELECT operation_id, owner_id, fencing_token, acquired_at, expires_at FROM {self._config.table_name} WHERE tenant_id = %s FOR UPDATE",
                (tid,),
            )
            row = cur.fetchone()
            if row is None:
                raise KeyError(f"missing tenant migration lock: {tid}")
            if str(row[0]) != oid or str(row[1]) != owner:
                raise PermissionError(f"tenant migration lock mismatch: tenant={tid}")
            current_expires_at = ensure_aware(row[4])
            if current_expires_at <= moment:
                raise KeyError(f"expired tenant migration lock: {tid}")
            expires_at = moment + timedelta(seconds=ttl)
            cur.execute(f"UPDATE {self._config.table_name} SET expires_at = %s WHERE tenant_id = %s", (expires_at, tid))
            conn.commit()
            lock = TenantMigrationLockRecord(tid, oid, owner, int(row[2]), row[3], expires_at)
            lock.validate()
            return lock

    def release(self, *, tenant_id: str, operation_id: str, owner_id: str) -> bool:
        tid = require_tenant_id(tenant_id)
        oid = str(operation_id or "").strip()
        owner = str(owner_id or "").strip()
        if not oid or not owner:
            raise ValueError("operation_id and owner_id are required")
        with self._connect() as conn, conn.cursor() as cur:
            self._tenant_lock(cur, tenant_id=tid)
            self._reap_expired_locked(cur, now=utc_now(), tenant_id=tid)
            cur.execute(f"SELECT operation_id, owner_id FROM {self._config.table_name} WHERE tenant_id = %s FOR UPDATE", (tid,))
            row = cur.fetchone()
            if row is None:
                conn.commit()
                return False
            if str(row[0]) != oid or str(row[1]) != owner:
                raise PermissionError(f"tenant migration lock mismatch: tenant={tid}")
            cur.execute(f"DELETE FROM {self._config.table_name} WHERE tenant_id = %s", (tid,))
            conn.commit()
            return True

    def get(self, *, tenant_id: str) -> TenantMigrationLockRecord | None:
        tid = require_tenant_id(tenant_id)
        moment = utc_now()
        with self._connect() as conn, conn.cursor() as cur:
            self._tenant_lock(cur, tenant_id=tid)
            self._reap_expired_locked(cur, now=moment, tenant_id=tid)
            cur.execute(
                f"SELECT tenant_id, operation_id, owner_id, fencing_token, acquired_at, expires_at FROM {self._config.table_name} WHERE tenant_id = %s",
                (tid,),
            )
            row = cur.fetchone()
            conn.commit()
            if row is None:
                return None
            lock = TenantMigrationLockRecord(row[0], row[1], row[2], int(row[3]), row[4], row[5])
            lock.validate()
            return lock

    def _next_token_locked(self, cur: Any, *, tenant_id: str) -> int:
        cur.execute(f"SELECT next_token FROM {self._config.token_table} WHERE tenant_id = %s FOR UPDATE", (tenant_id,))
        row = cur.fetchone()
        next_token = int(row[0]) + 1 if row is not None else 1
        cur.execute(
            f"INSERT INTO {self._config.token_table} (tenant_id, next_token) VALUES (%s, %s) ON CONFLICT (tenant_id) DO UPDATE SET next_token = EXCLUDED.next_token",
            (tenant_id, next_token),
        )
        return next_token

    @staticmethod
    def _tenant_lock(cur: Any, *, tenant_id: str) -> None:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (_advisory_lock_key(namespace="tenant-migration-lock", tenant_id=tenant_id),))

    def _reap_expired_locked(
        self,
        cur: Any,
        *,
        now: datetime,
        tenant_id: str | None = None,
    ) -> None:
        moment = ensure_aware(now)
        if tenant_id is None:
            cur.execute(
                f"DELETE FROM {self._config.table_name} WHERE expires_at <= %s",
                (moment,),
            )
            return
        tid = require_tenant_id(tenant_id)
        cur.execute(
            f"DELETE FROM {self._config.table_name} WHERE tenant_id = %s AND expires_at <= %s",
            (tid, moment),
        )

    def _connect(self):
        return self._psycopg.connect(self._config.dsn)

    def _init_db(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {self._config.table_name} (tenant_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL, owner_id TEXT NOT NULL, fencing_token BIGINT NOT NULL, acquired_at TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ NOT NULL)"
            )
            cur.execute(f"CREATE INDEX IF NOT EXISTS ix_{self._config.table_name}_expires_at ON {self._config.table_name}(expires_at)")
            cur.execute(f"CREATE TABLE IF NOT EXISTS {self._config.token_table} (tenant_id TEXT PRIMARY KEY, next_token BIGINT NOT NULL)")
            conn.commit()


__all__ = ["CANON_TENANT_MIGRATION_LOCK_POSTGRES", "PostgresTenantMigrationLockBackend", "PostgresTenantMigrationLockBackendConfig"]
