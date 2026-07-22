from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock
from time import monotonic, sleep

from core.tenancy.normalization import require_tenant_id
from runtime.platform.event_store.sqlite_platform import (
    SQLITE_ROW_FACTORY,
    SQLiteConnection,
    SQLiteOperationalError,
    SQLiteRow,
    connect_sqlite,
)
from tenancy.tenant_migration_lock_backend import (
    TenantMigrationLockBackend,
    TenantMigrationLockRecord,
    ensure_aware,
    utc_now,
)


CANON_TENANT_MIGRATION_LOCK_SQLITE = True

_SQLITE_BUSY_TIMEOUT_MS = 30_000
_WAL_BOOTSTRAP_BUSY_TIMEOUT_MS = 1_000
_WAL_BOOTSTRAP_TIMEOUT_SECONDS = 30.0
_WAL_BOOTSTRAP_RETRY_SECONDS = 0.05


def tenant_migration_lock_sqlite_path() -> Path:
    explicit = os.getenv(
        "BUSINESAIOS_TENANT_MIGRATION_LOCK_SQLITE_PATH",
        "",
    ).strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("BUSINESAIOS_TENANCY_DATA_DIR", "").strip()
    if data_dir:
        return Path(data_dir) / "tenant_migration_locks.sqlite3"
    base = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(base) / "tenancy" / "tenant_migration_locks.sqlite3"


class SQLiteTenantMigrationLockBackend(TenantMigrationLockBackend):
    def __init__(self, path: str | Path | None = None) -> None:
        self._path = (
            Path(path)
            if path is not None
            else tenant_migration_lock_sqlite_path()
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._init_db()

    def acquire(
        self,
        *,
        tenant_id: str,
        operation_id: str,
        owner_id: str,
        ttl_seconds: int,
        now: datetime | None = None,
    ) -> TenantMigrationLockRecord | None:
        tid = require_tenant_id(tenant_id)
        operation = str(operation_id or "").strip()
        owner = str(owner_id or "").strip()
        ttl = int(ttl_seconds)
        if not operation or not owner:
            raise ValueError("operation_id and owner_id are required")
        if ttl <= 0:
            raise ValueError("ttl_seconds must be > 0")
        moment = ensure_aware(now or utc_now())
        expires_at = moment + timedelta(seconds=ttl)
        with self._lock, self._session(write=True) as conn:
            self._reap_expired_locked(conn, now=moment)
            row = conn.execute(
                "SELECT tenant_id, operation_id, owner_id, fencing_token, "
                "acquired_at, expires_at FROM tenant_migration_locks "
                "WHERE tenant_id = ?",
                (tid,),
            ).fetchone()
            if row is not None:
                existing = self._row_to_record(row)
                if (
                    existing.operation_id == operation
                    and existing.owner_id == owner
                ):
                    conn.execute(
                        "UPDATE tenant_migration_locks SET expires_at = ? "
                        "WHERE tenant_id = ?",
                        (expires_at.isoformat(), tid),
                    )
                    reread = conn.execute(
                        "SELECT tenant_id, operation_id, owner_id, "
                        "fencing_token, acquired_at, expires_at "
                        "FROM tenant_migration_locks WHERE tenant_id = ?",
                        (tid,),
                    ).fetchone()
                    if reread is None:
                        raise RuntimeError(
                            "sqlite tenant migration lock renew lost record"
                        )
                    return self._row_to_record(reread)
                return None
            token = self._next_token_locked(conn, tenant_id=tid)
            conn.execute(
                "INSERT INTO tenant_migration_locks "
                "(tenant_id, operation_id, owner_id, fencing_token, "
                "acquired_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    tid,
                    operation,
                    owner,
                    token,
                    moment.isoformat(),
                    expires_at.isoformat(),
                ),
            )
            reread = conn.execute(
                "SELECT tenant_id, operation_id, owner_id, fencing_token, "
                "acquired_at, expires_at FROM tenant_migration_locks "
                "WHERE tenant_id = ?",
                (tid,),
            ).fetchone()
            if reread is None:
                raise RuntimeError(
                    "sqlite tenant migration lock insert did not persist"
                )
            return self._row_to_record(reread)

    def renew(
        self,
        *,
        tenant_id: str,
        operation_id: str,
        owner_id: str,
        ttl_seconds: int,
        now: datetime | None = None,
    ) -> TenantMigrationLockRecord:
        tid = require_tenant_id(tenant_id)
        operation = str(operation_id or "").strip()
        owner = str(owner_id or "").strip()
        ttl = int(ttl_seconds)
        if not operation or not owner:
            raise ValueError("operation_id and owner_id are required")
        if ttl <= 0:
            raise ValueError("ttl_seconds must be > 0")
        moment = ensure_aware(now or utc_now())
        expires_at = moment + timedelta(seconds=ttl)
        with self._lock, self._session(write=True) as conn:
            self._reap_expired_locked(conn, now=moment)
            row = conn.execute(
                "SELECT tenant_id, operation_id, owner_id, fencing_token, "
                "acquired_at, expires_at FROM tenant_migration_locks "
                "WHERE tenant_id = ?",
                (tid,),
            ).fetchone()
            if row is None:
                raise KeyError(f"missing tenant migration lock: {tid}")
            current = self._row_to_record(row)
            if (
                current.operation_id != operation
                or current.owner_id != owner
            ):
                raise PermissionError(
                    f"tenant migration lock mismatch: tenant={tid}"
                )
            conn.execute(
                "UPDATE tenant_migration_locks SET expires_at = ? "
                "WHERE tenant_id = ?",
                (expires_at.isoformat(), tid),
            )
            reread = conn.execute(
                "SELECT tenant_id, operation_id, owner_id, fencing_token, "
                "acquired_at, expires_at FROM tenant_migration_locks "
                "WHERE tenant_id = ?",
                (tid,),
            ).fetchone()
            if reread is None:
                raise RuntimeError(
                    "sqlite tenant migration lock renew lost record"
                )
            return self._row_to_record(reread)

    def release(
        self,
        *,
        tenant_id: str,
        operation_id: str,
        owner_id: str,
    ) -> bool:
        tid = require_tenant_id(tenant_id)
        operation = str(operation_id or "").strip()
        owner = str(owner_id or "").strip()
        if not operation or not owner:
            raise ValueError("operation_id and owner_id are required")
        with self._lock, self._session(write=True) as conn:
            self._reap_expired_locked(conn, now=utc_now())
            row = conn.execute(
                "SELECT operation_id, owner_id "
                "FROM tenant_migration_locks WHERE tenant_id = ?",
                (tid,),
            ).fetchone()
            if row is None:
                return False
            if str(row[0]) != operation or str(row[1]) != owner:
                raise PermissionError(
                    f"tenant migration lock mismatch: tenant={tid}"
                )
            conn.execute(
                "DELETE FROM tenant_migration_locks WHERE tenant_id = ?",
                (tid,),
            )
            return True

    def get(self, *, tenant_id: str) -> TenantMigrationLockRecord | None:
        tid = require_tenant_id(tenant_id)
        with self._lock, self._session(write=True) as conn:
            self._reap_expired_locked(conn, now=utc_now())
            row = conn.execute(
                "SELECT tenant_id, operation_id, owner_id, fencing_token, "
                "acquired_at, expires_at FROM tenant_migration_locks "
                "WHERE tenant_id = ?",
                (tid,),
            ).fetchone()
            return None if row is None else self._row_to_record(row)

    def _next_token_locked(
        self,
        conn: SQLiteConnection,
        *,
        tenant_id: str,
    ) -> int:
        row = conn.execute(
            "SELECT next_token FROM tenant_migration_lock_tokens "
            "WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
        next_token = int(row[0]) + 1 if row is not None else 1
        conn.execute(
            "INSERT INTO tenant_migration_lock_tokens "
            "(tenant_id, next_token) VALUES (?, ?) "
            "ON CONFLICT(tenant_id) DO UPDATE SET "
            "next_token = excluded.next_token",
            (tenant_id, next_token),
        )
        return next_token

    def _reap_expired_locked(
        self,
        conn: SQLiteConnection,
        *,
        now,
    ) -> None:
        conn.execute(
            "DELETE FROM tenant_migration_locks WHERE expires_at <= ?",
            (ensure_aware(now).isoformat(),),
        )

    @staticmethod
    def _row_to_record(row: SQLiteRow) -> TenantMigrationLockRecord:
        lock = TenantMigrationLockRecord(
            tenant_id=row[0],
            operation_id=row[1],
            owner_id=row[2],
            fencing_token=int(row[3]),
            acquired_at=ensure_aware(datetime.fromisoformat(row[4])),
            expires_at=ensure_aware(datetime.fromisoformat(row[5])),
        )
        lock.validate()
        return lock

    @contextmanager
    def _session(
        self,
        *,
        write: bool = False,
    ) -> Iterator[SQLiteConnection]:
        conn = self._connect(write=write)
        primary_error: BaseException | None = None
        try:
            try:
                yield conn
            except BaseException as exc:
                primary_error = exc
                try:
                    conn.rollback()
                except BaseException as rollback_exc:
                    exc.add_note(
                        "sqlite tenant migration lock rollback also failed: "
                        f"{rollback_exc}"
                    )
                raise
            try:
                conn.commit()
            except BaseException as exc:
                primary_error = exc
                try:
                    conn.rollback()
                except BaseException as rollback_exc:
                    exc.add_note(
                        "sqlite tenant migration lock rollback also failed: "
                        f"{rollback_exc}"
                    )
                raise
        finally:
            try:
                conn.close()
            except BaseException as close_exc:
                if primary_error is not None:
                    primary_error.add_note(
                        "sqlite tenant migration lock close also failed: "
                        f"{close_exc}"
                    )
                else:
                    raise

    def _connect(self, *, write: bool = False) -> SQLiteConnection:
        conn = connect_sqlite(
            self._path,
            timeout=_SQLITE_BUSY_TIMEOUT_MS / 1000.0,
            isolation_level=None,
        )
        try:
            conn.row_factory = SQLITE_ROW_FACTORY
            conn.execute(
                f"PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MS}"
            )
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            return conn
        except BaseException as exc:
            try:
                conn.close()
            except BaseException as close_exc:
                exc.add_note(
                    "sqlite tenant migration lock close also failed: "
                    f"{close_exc}"
                )
            raise

    @staticmethod
    def _is_busy_or_locked(exc: SQLiteOperationalError) -> bool:
        message = str(exc).lower()
        return "locked" in message or "busy" in message

    def _ensure_wal_mode(self) -> None:
        deadline = monotonic() + _WAL_BOOTSTRAP_TIMEOUT_SECONDS
        last_busy_error: SQLiteOperationalError | None = None
        while True:
            conn: SQLiteConnection | None = None
            primary_error: BaseException | None = None
            try:
                conn = connect_sqlite(
                    self._path,
                    timeout=_WAL_BOOTSTRAP_BUSY_TIMEOUT_MS / 1000.0,
                    isolation_level=None,
                )
                conn.row_factory = SQLITE_ROW_FACTORY
                conn.execute(
                    f"PRAGMA busy_timeout={_WAL_BOOTSTRAP_BUSY_TIMEOUT_MS}"
                )
                row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
                mode = (
                    str(row[0]).strip().lower()
                    if row is not None
                    else ""
                )
                if mode != "wal":
                    raise RuntimeError(
                        "sqlite tenant migration lock did not enable WAL mode"
                    )
                return
            except SQLiteOperationalError as exc:
                primary_error = exc
                if not self._is_busy_or_locked(exc):
                    raise
                last_busy_error = exc
            except BaseException as exc:
                primary_error = exc
                raise
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except BaseException as close_exc:
                        if primary_error is not None:
                            primary_error.add_note(
                                "sqlite tenant migration lock WAL close also "
                                f"failed: {close_exc}"
                            )
                        else:
                            raise

            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    "sqlite tenant migration lock WAL bootstrap timed out"
                ) from last_busy_error
            sleep(min(_WAL_BOOTSTRAP_RETRY_SECONDS, remaining))

    def schema_version(self) -> int:
        return 1

    def read_backend_clock(self) -> datetime:
        with self._lock, self._session() as conn:
            row = conn.execute(
                "SELECT strftime('%Y-%m-%dT%H:%M:%f+00:00','now')"
            ).fetchone()
        return ensure_aware(datetime.fromisoformat(str(row[0])))

    def _init_db(self) -> None:
        with self._lock:
            self._ensure_wal_mode()
            with self._session(write=True) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS tenant_migration_locks "
                    "(tenant_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL, "
                    "owner_id TEXT NOT NULL, fencing_token INTEGER NOT NULL, "
                    "acquired_at TEXT NOT NULL, expires_at TEXT NOT NULL)"
                )
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS "
                    "tenant_migration_lock_tokens "
                    "(tenant_id TEXT PRIMARY KEY, next_token INTEGER NOT NULL)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS "
                    "ix_tenant_migration_locks_expires_at "
                    "ON tenant_migration_locks(expires_at)"
                )


__all__ = [
    "CANON_TENANT_MIGRATION_LOCK_SQLITE",
    "SQLiteTenantMigrationLockBackend",
    "tenant_migration_lock_sqlite_path",
]
