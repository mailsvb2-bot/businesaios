from __future__ import annotations

import threading
from datetime import datetime

from core.tenancy.normalization import require_tenant_id
from reliability.distributed_lock_backend import (
    DistributedLockBackend,
    LockBackendRecord,
    build_expires_at,
    ensure_aware,
    normalize_lock_inputs,
    normalize_resource,
    normalize_ttl_seconds,
    safe_sql_identifier,
    utc_now,
)
from reliability.distributed_lock_contracts import LockLease
from storage.postgres_session import PostgresSession, PostgresSessionFactory


CANON_DISTRIBUTED_LOCK_POSTGRES = True


class PostgresDistributedLockBackend(DistributedLockBackend):
    def __init__(
        self,
        *,
        dsn: str,
        application_name: str = "businesaios-reliability-lock",
        statement_timeout_ms: int = 30000,
        lock_timeout_ms: int = 5000,
        table_prefix: str = "reliability",
    ) -> None:
        prefix = safe_sql_identifier(str(table_prefix or "reliability").strip())
        self._sessions = PostgresSessionFactory(
            dsn=str(dsn),
            application_name=str(
                application_name or "businesaios-reliability-lock"
            ),
            statement_timeout_ms=int(statement_timeout_ms),
            lock_timeout_ms=int(lock_timeout_ms),
        )
        self._locks_table = safe_sql_identifier(
            f"{prefix}_distributed_locks"
        )
        self._tokens_table = safe_sql_identifier(f"{prefix}_lock_tokens")
        self._schema_lock = threading.Lock()
        self._schema_ready = False

    def ping(self) -> bool:
        try:
            with self._sessions.open() as session:
                row = session.fetchone("SELECT 1 AS ok;")
                return bool(row and int(row["ok"]) == 1)
        except Exception:
            return False

    @staticmethod
    def _rollback_preserving(
        session: PostgresSession,
        primary_error: BaseException,
    ) -> None:
        try:
            session.rollback()
        except BaseException as rollback_error:
            primary_error.add_note(
                f"distributed lock rollback also failed: {rollback_error}"
            )

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            with self._sessions.open() as session:
                try:
                    session.execute(
                        f"CREATE TABLE IF NOT EXISTS {self._tokens_table} ("
                        "tenant_id TEXT NOT NULL, "
                        "resource TEXT NOT NULL, "
                        "last_token BIGINT NOT NULL, "
                        "updated_at TIMESTAMPTZ NOT NULL, "
                        "PRIMARY KEY (tenant_id, resource));"
                    )
                    session.execute(
                        f"CREATE TABLE IF NOT EXISTS {self._locks_table} ("
                        "tenant_id TEXT NOT NULL, "
                        "resource TEXT NOT NULL, "
                        "owner_id TEXT NOT NULL, "
                        "fencing_token BIGINT NOT NULL, "
                        "acquired_at TIMESTAMPTZ NOT NULL, "
                        "expires_at TIMESTAMPTZ NOT NULL, "
                        "PRIMARY KEY (tenant_id, resource));"
                    )
                    session.execute(
                        f"CREATE INDEX IF NOT EXISTS "
                        f"idx_{self._locks_table}_expires_at "
                        f"ON {self._locks_table}(expires_at);"
                    )
                    session.commit()
                except Exception as exc:
                    self._rollback_preserving(session, exc)
                    raise
            self._schema_ready = True

    def _lock_token_row_in_tx(
        self,
        *,
        session: PostgresSession,
        tenant_id: str,
        resource: str,
        now: datetime,
    ) -> int:
        """Serialize every contender before it observes the current lease."""

        session.execute(
            f"INSERT INTO {self._tokens_table} "
            "(tenant_id, resource, last_token, updated_at) "
            "VALUES (%s, %s, 0, %s) "
            "ON CONFLICT (tenant_id, resource) DO NOTHING;",
            (tenant_id, resource, now),
        )
        row = session.fetchone(
            f"SELECT last_token FROM {self._tokens_table} "
            "WHERE tenant_id=%s AND resource=%s FOR UPDATE;",
            (tenant_id, resource),
        )
        if row is None:
            raise RuntimeError("failed to lock fencing token row")
        return int(row["last_token"])

    def _next_token_in_tx(
        self,
        *,
        session: PostgresSession,
        tenant_id: str,
        resource: str,
        now: datetime,
    ) -> int:
        row = session.fetchone(
            f"UPDATE {self._tokens_table} "
            "SET last_token = last_token + 1, updated_at = %s "
            "WHERE tenant_id=%s AND resource=%s "
            "RETURNING last_token;",
            (now, tenant_id, resource),
        )
        if row is None:
            raise RuntimeError("failed to allocate fencing token")
        return int(row["last_token"])

    def _ensure_token_floor_in_tx(
        self,
        *,
        session: PostgresSession,
        tenant_id: str,
        resource: str,
        minimum_token: int,
        current_token: int,
        now: datetime,
    ) -> tuple[int, bool]:
        floor = int(minimum_token)
        token = int(current_token)
        if token >= floor:
            return token, False
        row = session.fetchone(
            f"UPDATE {self._tokens_table} "
            "SET last_token = GREATEST(last_token, %s), updated_at = %s "
            "WHERE tenant_id=%s AND resource=%s "
            "RETURNING last_token;",
            (floor, now, tenant_id, resource),
        )
        if row is None:
            raise RuntimeError("failed to restore fencing token floor")
        restored = int(row["last_token"])
        if restored < floor:
            raise RuntimeError("fencing token floor restoration regressed")
        return restored, True

    @staticmethod
    def _row_to_lease(row: dict[str, object]) -> LockLease:
        return LockBackendRecord(
            tenant_id=str(row["tenant_id"]),
            resource=str(row["resource"]),
            owner_id=str(row["owner_id"]),
            fencing_token=int(row["fencing_token"]),
            acquired_at=ensure_aware(row["acquired_at"]),  # type: ignore[arg-type]
            expires_at=ensure_aware(row["expires_at"]),  # type: ignore[arg-type]
        ).to_lease()

    def acquire(
        self,
        *,
        tenant_id: str,
        resource: str,
        owner_id: str,
        ttl_seconds: int = 30,
        now: datetime | None = None,
    ) -> LockLease | None:
        tid, res, owner, ttl, moment = normalize_lock_inputs(
            tenant_id=tenant_id,
            resource=resource,
            owner_id=owner_id,
            ttl_seconds=ttl_seconds,
            now=now,
        )
        expires_at = build_expires_at(now=moment, ttl_seconds=ttl)
        self._ensure_schema()

        with self._sessions.open() as session:
            try:
                last_token = self._lock_token_row_in_tx(
                    session=session,
                    tenant_id=tid,
                    resource=res,
                    now=moment,
                )
                current = session.fetchone(
                    f"SELECT tenant_id, resource, owner_id, fencing_token, "
                    f"acquired_at, expires_at FROM {self._locks_table} "
                    "WHERE tenant_id=%s AND resource=%s FOR UPDATE;",
                    (tid, res),
                )
                if current is not None:
                    current_lease = self._row_to_lease(current)
                    last_token, repaired = self._ensure_token_floor_in_tx(
                        session=session,
                        tenant_id=tid,
                        resource=res,
                        minimum_token=current_lease.fencing_token,
                        current_token=last_token,
                        now=moment,
                    )
                    if current_lease.is_live(now=moment):
                        if repaired:
                            session.commit()
                        else:
                            session.rollback()
                        return None

                token = self._next_token_in_tx(
                    session=session,
                    tenant_id=tid,
                    resource=res,
                    now=moment,
                )
                session.execute(
                    f"INSERT INTO {self._locks_table} "
                    "(tenant_id, resource, owner_id, fencing_token, "
                    "acquired_at, expires_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (tenant_id, resource) DO UPDATE SET "
                    "owner_id = EXCLUDED.owner_id, "
                    "fencing_token = EXCLUDED.fencing_token, "
                    "acquired_at = EXCLUDED.acquired_at, "
                    "expires_at = EXCLUDED.expires_at;",
                    (tid, res, owner, token, moment, expires_at),
                )
                session.commit()
            except Exception as exc:
                self._rollback_preserving(session, exc)
                raise

        return LockBackendRecord(
            tenant_id=tid,
            resource=res,
            owner_id=owner,
            fencing_token=token,
            acquired_at=moment,
            expires_at=expires_at,
        ).to_lease()

    def renew(
        self,
        *,
        lease: LockLease,
        ttl_seconds: int = 30,
        now: datetime | None = None,
    ) -> LockLease:
        lease.validate()
        ttl = normalize_ttl_seconds(ttl_seconds)
        moment = ensure_aware(now or utc_now())
        expires_at = build_expires_at(now=moment, ttl_seconds=ttl)
        self._ensure_schema()

        with self._sessions.open() as session:
            try:
                row = session.fetchone(
                    f"SELECT tenant_id, resource, owner_id, fencing_token, "
                    f"acquired_at, expires_at FROM {self._locks_table} "
                    "WHERE tenant_id=%s AND resource=%s FOR UPDATE;",
                    (lease.tenant_id, lease.resource),
                )
                if row is None:
                    raise PermissionError("lease no longer exists")
                current = self._row_to_lease(row)
                if current.owner_id != lease.owner_id:
                    raise PermissionError("lease ownership mismatch")
                if current.fencing_token != lease.fencing_token:
                    raise PermissionError("lease fencing token mismatch")
                if not current.is_live(now=moment):
                    raise PermissionError("lease has expired")

                session.execute(
                    f"UPDATE {self._locks_table} SET expires_at=%s "
                    "WHERE tenant_id=%s AND resource=%s "
                    "AND owner_id=%s AND fencing_token=%s;",
                    (
                        expires_at,
                        current.tenant_id,
                        current.resource,
                        current.owner_id,
                        current.fencing_token,
                    ),
                )
                session.commit()
            except Exception as exc:
                self._rollback_preserving(session, exc)
                raise

        return LockBackendRecord(
            tenant_id=current.tenant_id,
            resource=current.resource,
            owner_id=current.owner_id,
            fencing_token=current.fencing_token,
            acquired_at=current.acquired_at,
            expires_at=expires_at,
        ).to_lease()

    def release(self, *, lease: LockLease) -> None:
        lease.validate()
        self._ensure_schema()
        with self._sessions.open() as session:
            try:
                session.execute(
                    f"DELETE FROM {self._locks_table} "
                    "WHERE tenant_id=%s AND resource=%s "
                    "AND owner_id=%s AND fencing_token=%s;",
                    (
                        lease.tenant_id,
                        lease.resource,
                        lease.owner_id,
                        lease.fencing_token,
                    ),
                )
                session.commit()
            except Exception as exc:
                self._rollback_preserving(session, exc)
                raise

    def get(self, *, tenant_id: str, resource: str) -> LockLease | None:
        tid = require_tenant_id(tenant_id)
        res = normalize_resource(resource)
        moment = ensure_aware(utc_now())
        self._ensure_schema()

        with self._sessions.open() as session:
            row = session.fetchone(
                f"SELECT tenant_id, resource, owner_id, fencing_token, "
                f"acquired_at, expires_at FROM {self._locks_table} "
                "WHERE tenant_id=%s AND resource=%s;",
                (tid, res),
            )
            if row is None:
                return None
            lease = self._row_to_lease(row)
            if lease.is_live(now=moment):
                return lease
            try:
                session.execute(
                    f"DELETE FROM {self._locks_table} "
                    "WHERE tenant_id=%s AND resource=%s "
                    "AND fencing_token=%s AND expires_at <= %s;",
                    (
                        lease.tenant_id,
                        lease.resource,
                        lease.fencing_token,
                        moment,
                    ),
                )
                session.commit()
            except Exception as exc:
                self._rollback_preserving(session, exc)
            return None


__all__ = [
    "CANON_DISTRIBUTED_LOCK_POSTGRES",
    "PostgresDistributedLockBackend",
]
