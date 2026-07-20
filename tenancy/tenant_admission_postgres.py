from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from collections.abc import Mapping
from typing import Any

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_admission_contract import (
    TenantAdmissionBackend,
    TenantAdmissionLease,
    TenantAdmissionRequest,
    TenantAdmissionVerdict,
)


CANON_TENANT_ADMISSION_POSTGRES = True
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
class PostgresTenantAdmissionBackendConfig:
    dsn: str
    table_name: str = "tenant_admission_leases"
    token_table: str = "tenant_admission_fencing"

    def validate(self) -> None:
        if not str(self.dsn or "").strip():
            raise ValueError("dsn is required")
        _safe_identifier(self.table_name, field_name="table_name")
        _safe_identifier(self.token_table, field_name="token_table")


class PostgresTenantAdmissionBackend(TenantAdmissionBackend):
    def __init__(self, config: PostgresTenantAdmissionBackendConfig) -> None:
        config.validate()
        self._config = config
        try:
            import psycopg
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgresTenantAdmissionBackend") from exc
        self._psycopg = psycopg
        self._init_db()

    def admit(self, *, request: TenantAdmissionRequest, limit: int) -> TenantAdmissionVerdict:
        request.validate()
        max_active = max(0, int(limit))
        moment = request.requested_at.astimezone(timezone.utc)
        expires_at = moment + timedelta(seconds=int(request.ttl_seconds))
        with self._connect() as conn, conn.cursor() as cur:
            self._tenant_lock(cur, tenant_id=request.tenant_id)
            self._reap_expired_locked(cur, now=moment, tenant_id=request.tenant_id)
            cur.execute(
                f"SELECT owner_id, labels_json, fencing_token, acquired_at, expires_at FROM {self._config.table_name} "
                "WHERE tenant_id = %s AND run_id = %s FOR UPDATE",
                (request.tenant_id, request.run_id),
            )
            row = cur.fetchone()
            active_runs = self._active_count_locked(cur, tenant_id=request.tenant_id)
            if row is not None:
                if str(row[0]) != request.owner_id:
                    conn.commit()
                    return TenantAdmissionVerdict(False, "lease_owned_by_another_owner", request.tenant_id, request.run_id, active_runs, max_active, None)
                if self._decode_labels(row[1]) != dict(request.labels):
                    conn.commit()
                    return TenantAdmissionVerdict(False, "lease_labels_mismatch", request.tenant_id, request.run_id, active_runs, max_active, None)
                lease = self._renew_locked(
                    cur,
                    tenant_id=request.tenant_id,
                    run_id=request.run_id,
                    owner_id=request.owner_id,
                    ttl_seconds=request.ttl_seconds,
                    now=moment,
                )
                conn.commit()
                return TenantAdmissionVerdict(True, "already_acquired", request.tenant_id, request.run_id, active_runs, max_active, lease)
            if max_active <= 0:
                conn.commit()
                return TenantAdmissionVerdict(False, "tenant_runtime_disabled", request.tenant_id, request.run_id, active_runs, max_active, None)
            if active_runs >= max_active:
                conn.commit()
                return TenantAdmissionVerdict(False, "tenant_runtime_capacity_exceeded", request.tenant_id, request.run_id, active_runs, max_active, None)
            token = self._next_token_locked(cur, tenant_id=request.tenant_id)
            cur.execute(
                f"INSERT INTO {self._config.table_name} "
                "(tenant_id, run_id, owner_id, fencing_token, acquired_at, heartbeat_at, expires_at, labels_json) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    request.tenant_id,
                    request.run_id,
                    request.owner_id,
                    token,
                    moment,
                    moment,
                    expires_at,
                    json.dumps(dict(request.labels), sort_keys=True, separators=(",", ":")),
                ),
            )
            conn.commit()
            lease = TenantAdmissionLease(request.tenant_id, request.run_id, request.owner_id, int(token), moment, expires_at)
            lease.validate()
            return TenantAdmissionVerdict(True, "acquired", request.tenant_id, request.run_id, active_runs + 1, max_active, lease)

    def renew(self, *, tenant_id: str, run_id: str, owner_id: str, ttl_seconds: int) -> TenantAdmissionLease:
        tid = require_tenant_id(tenant_id)
        rid = str(run_id or "").strip()
        oid = str(owner_id or "").strip()
        if not rid or not oid:
            raise ValueError("run_id and owner_id are required")
        moment = datetime.now(timezone.utc)
        with self._connect() as conn, conn.cursor() as cur:
            self._tenant_lock(cur, tenant_id=tid)
            self._reap_expired_locked(cur, now=moment, tenant_id=tid)
            lease = self._renew_locked(cur, tenant_id=tid, run_id=rid, owner_id=oid, ttl_seconds=ttl_seconds, now=moment)
            conn.commit()
            return lease

    def release(self, *, tenant_id: str, run_id: str, owner_id: str) -> bool:
        tid = require_tenant_id(tenant_id)
        rid = str(run_id or "").strip()
        oid = str(owner_id or "").strip()
        if not rid or not oid:
            raise ValueError("run_id and owner_id are required")
        with self._connect() as conn, conn.cursor() as cur:
            self._tenant_lock(cur, tenant_id=tid)
            self._reap_expired_locked(cur, now=datetime.now(timezone.utc), tenant_id=tid)
            cur.execute(f"SELECT owner_id FROM {self._config.table_name} WHERE tenant_id = %s AND run_id = %s FOR UPDATE", (tid, rid))
            row = cur.fetchone()
            if row is None:
                conn.commit()
                return False
            if str(row[0]) != oid:
                raise PermissionError(f"tenant admission lease owner mismatch: tenant={tid} run_id={rid}")
            cur.execute(f"DELETE FROM {self._config.table_name} WHERE tenant_id = %s AND run_id = %s", (tid, rid))
            conn.commit()
            return True

    def list_active(self, *, tenant_id: str) -> tuple[TenantAdmissionLease, ...]:
        tid = require_tenant_id(tenant_id)
        moment = datetime.now(timezone.utc)
        with self._connect() as conn, conn.cursor() as cur:
            self._tenant_lock(cur, tenant_id=tid)
            self._reap_expired_locked(cur, now=moment, tenant_id=tid)
            cur.execute(
                f"SELECT tenant_id, run_id, owner_id, fencing_token, acquired_at, expires_at FROM {self._config.table_name} "
                "WHERE tenant_id = %s ORDER BY acquired_at, run_id",
                (tid,),
            )
            rows = cur.fetchall()
            conn.commit()
            leases = [TenantAdmissionLease(row[0], row[1], row[2], int(row[3]), row[4], row[5]) for row in rows]
            for lease in leases:
                lease.validate()
            return tuple(leases)

    def _renew_locked(
        self,
        cur: Any,
        *,
        tenant_id: str,
        run_id: str,
        owner_id: str,
        ttl_seconds: int,
        now: datetime,
    ) -> TenantAdmissionLease:
        ttl = int(ttl_seconds)
        if ttl <= 0:
            raise ValueError("ttl_seconds must be > 0")
        cur.execute(
            f"SELECT owner_id, fencing_token, acquired_at, expires_at FROM {self._config.table_name} WHERE tenant_id = %s AND run_id = %s FOR UPDATE",
            (tenant_id, run_id),
        )
        row = cur.fetchone()
        if row is None:
            raise KeyError(f"missing tenant admission lease: tenant={tenant_id} run_id={run_id}")
        if str(row[0]) != owner_id:
            raise PermissionError(f"tenant admission lease owner mismatch: tenant={tenant_id} run_id={run_id}")
        current_expires_at = self._ensure_aware(row[3], field_name="expires_at")
        if current_expires_at <= now:
            raise KeyError(f"expired tenant admission lease: tenant={tenant_id} run_id={run_id}")
        expires_at = now + timedelta(seconds=ttl)
        cur.execute(
            f"UPDATE {self._config.table_name} SET heartbeat_at = %s, expires_at = %s WHERE tenant_id = %s AND run_id = %s",
            (now, expires_at, tenant_id, run_id),
        )
        lease = TenantAdmissionLease(tenant_id, run_id, owner_id, int(row[1]), row[2], expires_at)
        lease.validate()
        return lease

    def _active_count_locked(self, cur: Any, *, tenant_id: str) -> int:
        cur.execute(f"SELECT COUNT(*) FROM {self._config.table_name} WHERE tenant_id = %s", (tenant_id,))
        row = cur.fetchone()
        return int(row[0] if row is not None else 0)

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
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (_advisory_lock_key(namespace="tenant-admission", tenant_id=tenant_id),))

    def _reap_expired_locked(
        self,
        cur: Any,
        *,
        now: datetime,
        tenant_id: str | None = None,
    ) -> None:
        moment = self._ensure_aware(now, field_name="now")
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

    @staticmethod
    def _ensure_aware(value: datetime, *, field_name: str) -> datetime:
        if not isinstance(value, datetime):
            raise TypeError(f"{field_name} must be a datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} must be timezone-aware")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _decode_labels(value: Any) -> dict[str, Any]:
        if value in (None, ""):
            return {}
        decoded = json.loads(value) if isinstance(value, str) else value
        if not isinstance(decoded, Mapping):
            raise ValueError("labels_json must decode to a mapping")
        return dict(decoded)

    def _init_db(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {self._config.table_name} ("
                "tenant_id TEXT NOT NULL, run_id TEXT NOT NULL, owner_id TEXT NOT NULL, fencing_token BIGINT NOT NULL, acquired_at TIMESTAMPTZ NOT NULL, heartbeat_at TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ NOT NULL, labels_json JSONB NOT NULL, PRIMARY KEY (tenant_id, run_id))"
            )
            cur.execute(f"CREATE INDEX IF NOT EXISTS ix_{self._config.table_name}_expires_at ON {self._config.table_name}(expires_at)")
            cur.execute(f"CREATE TABLE IF NOT EXISTS {self._config.token_table} (tenant_id TEXT PRIMARY KEY, next_token BIGINT NOT NULL)")
            conn.commit()

    def _connect(self):
        return self._psycopg.connect(self._config.dsn)


__all__ = ["CANON_TENANT_ADMISSION_POSTGRES", "PostgresTenantAdmissionBackend", "PostgresTenantAdmissionBackendConfig"]
