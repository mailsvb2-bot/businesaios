from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from multiprocessing import get_context
from pathlib import Path
from threading import Barrier, Thread

import pytest

import tenancy.tenant_migration_lock_sqlite as sqlite_module
from tenancy.tenant_migration_lock import TenantMigrationLockService
from tenancy.tenant_migration_lock_backend import (
    TenantMigrationLockBackend,
    TenantMigrationLockRecord,
    ensure_aware,
)
from tenancy.tenant_migration_lock_sqlite import SQLiteTenantMigrationLockBackend


NOW = datetime(2026, 7, 22, 8, 0, tzinfo=UTC)


def _acquire_in_process(path: str, owner: str, gate, results) -> None:
    backend = SQLiteTenantMigrationLockBackend(path)
    gate.wait(10)
    lock = backend.acquire(
        tenant_id="tenant-a",
        operation_id="migration",
        owner_id=owner,
        ttl_seconds=60,
        now=NOW,
    )
    results.put(None if lock is None else (lock.owner_id, lock.fencing_token))


def test_path_precedence_and_backend_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    explicit = tmp_path / "explicit.sqlite3"
    monkeypatch.setenv("BUSINESAIOS_TENANT_MIGRATION_LOCK_SQLITE_PATH", str(explicit))
    monkeypatch.setenv("BUSINESAIOS_TENANCY_DATA_DIR", str(tmp_path / "tenancy-data"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    assert sqlite_module.tenant_migration_lock_sqlite_path() == explicit

    monkeypatch.delenv("BUSINESAIOS_TENANT_MIGRATION_LOCK_SQLITE_PATH")
    assert sqlite_module.tenant_migration_lock_sqlite_path() == tmp_path / "tenancy-data" / "tenant_migration_locks.sqlite3"

    monkeypatch.delenv("BUSINESAIOS_TENANCY_DATA_DIR")
    assert sqlite_module.tenant_migration_lock_sqlite_path() == tmp_path / "data" / "tenancy" / "tenant_migration_locks.sqlite3"

    monkeypatch.setenv("DATA_DIR", "   ")
    assert sqlite_module.tenant_migration_lock_sqlite_path() == Path("data/tenancy/tenant_migration_locks.sqlite3")

    backend = SQLiteTenantMigrationLockBackend(tmp_path / "nested" / "locks.sqlite3")
    assert backend.schema_version() == 1
    clock = backend.read_backend_clock()
    assert clock.tzinfo is not None and clock.utcoffset() == timedelta(0)


def test_backend_validation_and_complete_lock_lifecycle(tmp_path: Path) -> None:
    backend = SQLiteTenantMigrationLockBackend(tmp_path / "locks.sqlite3")

    for kwargs in (
        {"tenant_id": "default", "operation_id": "op", "owner_id": "owner", "ttl_seconds": 1},
        {"tenant_id": "tenant-a", "operation_id": "", "owner_id": "owner", "ttl_seconds": 1},
        {"tenant_id": "tenant-a", "operation_id": "op", "owner_id": "", "ttl_seconds": 1},
        {"tenant_id": "tenant-a", "operation_id": "op", "owner_id": "owner", "ttl_seconds": 0},
    ):
        with pytest.raises(ValueError):
            backend.acquire(**kwargs, now=NOW)

    first = backend.acquire(
        tenant_id="tenant-a", operation_id="migration-1", owner_id="worker-a", ttl_seconds=60, now=NOW
    )
    assert first is not None
    assert first.fencing_token == 1
    assert first.acquired_at == NOW
    assert first.expires_at == NOW + timedelta(seconds=60)
    assert backend.get(tenant_id="tenant-a") == first

    conflict = backend.acquire(
        tenant_id="tenant-a", operation_id="migration-2", owner_id="worker-b", ttl_seconds=60, now=NOW
    )
    assert conflict is None

    extended = backend.acquire(
        tenant_id="tenant-a",
        operation_id="migration-1",
        owner_id="worker-a",
        ttl_seconds=120,
        now=NOW + timedelta(seconds=10),
    )
    assert extended is not None
    assert extended.fencing_token == first.fencing_token
    assert extended.acquired_at == first.acquired_at
    assert extended.expires_at == NOW + timedelta(seconds=130)

    for kwargs in (
        {"operation_id": "", "owner_id": "worker-a", "ttl_seconds": 1},
        {"operation_id": "migration-1", "owner_id": "", "ttl_seconds": 1},
        {"operation_id": "migration-1", "owner_id": "worker-a", "ttl_seconds": 0},
    ):
        with pytest.raises(ValueError):
            backend.renew(tenant_id="tenant-a", now=NOW, **kwargs)

    with pytest.raises(PermissionError, match="mismatch"):
        backend.renew(
            tenant_id="tenant-a", operation_id="migration-1", owner_id="other", ttl_seconds=60, now=NOW
        )

    renewed = backend.renew(
        tenant_id="tenant-a",
        operation_id="migration-1",
        owner_id="worker-a",
        ttl_seconds=30,
        now=NOW + timedelta(seconds=20),
    )
    assert renewed.expires_at == NOW + timedelta(seconds=50)
    assert renewed.fencing_token == 1

    for operation_id, owner_id in (("", "worker-a"), ("migration-1", "")):
        with pytest.raises(ValueError):
            backend.release(tenant_id="tenant-a", operation_id=operation_id, owner_id=owner_id)
    with pytest.raises(PermissionError, match="mismatch"):
        backend.release(tenant_id="tenant-a", operation_id="migration-1", owner_id="other")
    assert backend.release(tenant_id="tenant-a", operation_id="migration-1", owner_id="worker-a") is True
    assert backend.release(tenant_id="tenant-a", operation_id="migration-1", owner_id="worker-a") is False

    expired = backend.acquire(
        tenant_id="tenant-a", operation_id="migration-3", owner_id="worker-c", ttl_seconds=1, now=NOW
    )
    assert expired is not None and expired.fencing_token == 2
    with pytest.raises(KeyError, match="missing"):
        backend.renew(
            tenant_id="tenant-a",
            operation_id="migration-3",
            owner_id="worker-c",
            ttl_seconds=10,
            now=NOW + timedelta(seconds=2),
        )

    replacement = backend.acquire(
        tenant_id="tenant-a",
        operation_id="migration-4",
        owner_id="worker-d",
        ttl_seconds=10,
        now=NOW + timedelta(seconds=2),
    )
    assert replacement is not None and replacement.fencing_token == 3


def test_two_backend_instances_serialize_competing_acquire(tmp_path: Path) -> None:
    path = tmp_path / "locks.sqlite3"
    first = SQLiteTenantMigrationLockBackend(path)
    second = SQLiteTenantMigrationLockBackend(path)
    barrier = Barrier(3)
    results: list[object] = []
    errors: list[BaseException] = []

    def acquire(backend: SQLiteTenantMigrationLockBackend, owner: str) -> None:
        try:
            barrier.wait(timeout=5)
            results.append(
                backend.acquire(
                    tenant_id="tenant-a",
                    operation_id="migration",
                    owner_id=owner,
                    ttl_seconds=60,
                    now=NOW,
                )
            )
        except BaseException as exc:
            errors.append(exc)

    threads = [Thread(target=acquire, args=(first, "a")), Thread(target=acquire, args=(second, "b"))]
    for thread in threads:
        thread.start()
    barrier.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=10)
    assert errors == []
    assert sum(item is not None for item in results) == 1
    assert sum(item is None for item in results) == 1


def test_two_processes_serialize_competing_acquire(tmp_path: Path) -> None:
    context = get_context("spawn")
    gate = context.Event()
    results = context.Queue()
    path = str(tmp_path / "locks.sqlite3")
    processes = [
        context.Process(target=_acquire_in_process, args=(path, owner, gate, results))
        for owner in ("process-a", "process-b")
    ]
    for process in processes:
        process.start()
    gate.set()
    for process in processes:
        process.join(timeout=20)
        assert process.exitcode == 0
    values = [results.get(timeout=5), results.get(timeout=5)]
    assert sum(value is not None for value in values) == 1
    assert sum(value is None for value in values) == 1
    assert next(value for value in values if value is not None)[1] == 1


def test_record_backend_helpers_and_protocol_surface() -> None:
    assert ensure_aware(NOW) == NOW
    with pytest.raises(TypeError, match="datetime"):
        ensure_aware("now")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="timezone-aware"):
        ensure_aware(datetime(2026, 1, 1))

    valid = TenantMigrationLockRecord("tenant-a", "op", "owner", 1, NOW, NOW + timedelta(seconds=1))
    valid.validate()
    invalid_records = (
        TenantMigrationLockRecord("default", "op", "owner", 1, NOW, NOW + timedelta(seconds=1)),
        TenantMigrationLockRecord("tenant-a", "", "owner", 1, NOW, NOW + timedelta(seconds=1)),
        TenantMigrationLockRecord("tenant-a", "op", "", 1, NOW, NOW + timedelta(seconds=1)),
        TenantMigrationLockRecord("tenant-a", "op", "owner", 0, NOW, NOW + timedelta(seconds=1)),
        TenantMigrationLockRecord("tenant-a", "op", "owner", 1, datetime(2026, 1, 1), NOW),
        TenantMigrationLockRecord("tenant-a", "op", "owner", 1, NOW, NOW),
    )
    for record in invalid_records:
        with pytest.raises((ValueError, TypeError)):
            record.validate()

    assert TenantMigrationLockBackend.acquire(object(), tenant_id="t", operation_id="o", owner_id="x", ttl_seconds=1) is None
    assert TenantMigrationLockBackend.renew(object(), tenant_id="t", operation_id="o", owner_id="x", ttl_seconds=1) is None
    assert TenantMigrationLockBackend.release(object(), tenant_id="t", operation_id="o", owner_id="x") is None
    assert TenantMigrationLockBackend.get(object(), tenant_id="t") is None


class Registry:
    def __init__(self) -> None:
        self.required: list[str] = []

    def require(self, tenant_id: str):
        self.required.append(tenant_id)
        return object()


class Backend:
    def __init__(self) -> None:
        self.lock = TenantMigrationLockRecord("tenant-a", "op", "owner", 1, NOW, NOW + timedelta(seconds=10))
        self.allow = True
        self.calls: list[tuple[str, dict]] = []

    def acquire(self, **kwargs):
        self.calls.append(("acquire", kwargs))
        return self.lock if self.allow else None

    def renew(self, **kwargs):
        self.calls.append(("renew", kwargs))
        return self.lock

    def release(self, **kwargs):
        self.calls.append(("release", kwargs))
        return True

    def get(self, **kwargs):
        self.calls.append(("get", kwargs))
        return self.lock


def test_service_preserves_registry_and_backend_contracts() -> None:
    backend = Backend()
    registry = Registry()
    service = TenantMigrationLockService(backend=backend, tenant_registry=registry)
    verdict = service.acquire(tenant_id=" tenant-a ", operation_id="op", owner_id="owner", ttl_seconds=10)
    assert verdict.allowed is True and verdict.reason == "acquired" and verdict.lock == backend.lock
    assert registry.required == ["tenant-a"]

    backend.allow = False
    denied = service.acquire(tenant_id="tenant-a", operation_id="op2", owner_id="other", ttl_seconds=10)
    assert denied.allowed is False and denied.reason == "tenant_migration_locked" and denied.lock == backend.lock

    assert service.renew(tenant_id="tenant-a", operation_id="op", owner_id="owner", ttl_seconds=10) == backend.lock
    assert service.release(tenant_id="tenant-a", operation_id="op", owner_id="owner") is True
    assert service.get(tenant_id="tenant-a") == backend.lock

    no_registry = TenantMigrationLockService(backend=backend)
    assert no_registry.acquire(tenant_id="tenant-a", operation_id="op", owner_id="owner", ttl_seconds=10).allowed is False


class FakeCursorResult:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class FakeStoreConnection:
    def __init__(self, rows: list[object | None]):
        self.rows = list(rows)
        self.executions: list[tuple[str, object]] = []

    def execute(self, sql, params=()):
        self.executions.append((sql, params))
        row = self.rows.pop(0) if self.rows else None
        return FakeCursorResult(row)


@contextmanager
def session(conn):
    yield conn


def test_persistence_impossibility_guards_and_row_projection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend = SQLiteTenantMigrationLockBackend(tmp_path / "locks.sqlite3")

    existing_row = ("tenant-a", "op", "owner", 1, NOW.isoformat(), (NOW + timedelta(seconds=10)).isoformat())
    lost_renew = FakeStoreConnection([None, existing_row, None, None])
    monkeypatch.setattr(backend, "_session", lambda **_: session(lost_renew))
    with pytest.raises(RuntimeError, match="renew lost record"):
        backend.acquire(tenant_id="tenant-a", operation_id="op", owner_id="owner", ttl_seconds=10, now=NOW)

    lost_insert = FakeStoreConnection([None, None, None, None, None])
    monkeypatch.setattr(backend, "_session", lambda **_: session(lost_insert))
    with pytest.raises(RuntimeError, match="insert did not persist"):
        backend.acquire(tenant_id="tenant-a", operation_id="op", owner_id="owner", ttl_seconds=10, now=NOW)

    missing_renew = FakeStoreConnection([None, None])
    monkeypatch.setattr(backend, "_session", lambda **_: session(missing_renew))
    with pytest.raises(KeyError, match="missing"):
        backend.renew(tenant_id="tenant-a", operation_id="op", owner_id="owner", ttl_seconds=10, now=NOW)

    lost_explicit_renew = FakeStoreConnection([None, existing_row, None, None])
    monkeypatch.setattr(backend, "_session", lambda **_: session(lost_explicit_renew))
    with pytest.raises(RuntimeError, match="renew lost record"):
        backend.renew(tenant_id="tenant-a", operation_id="op", owner_id="owner", ttl_seconds=10, now=NOW)

    with pytest.raises(ValueError, match="fencing_token"):
        backend._row_to_record(("tenant-a", "op", "owner", 0, NOW.isoformat(), (NOW + timedelta(seconds=1)).isoformat()))


class FakeConnection:
    def __init__(self) -> None:
        self.row_factory = None
        self.executions: list[str] = []
        self.in_transaction = True
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0
        self.execute_error: BaseException | None = None
        self.commit_error: BaseException | None = None
        self.rollback_error: BaseException | None = None
        self.close_error: BaseException | None = None

    def execute(self, sql):
        self.executions.append(sql)
        if self.execute_error is not None:
            raise self.execute_error
        return FakeCursorResult(("2026-07-22T08:00:00.000+00:00",))

    def commit(self):
        self.commits += 1
        self.in_transaction = False
        if self.commit_error is not None:
            raise self.commit_error

    def rollback(self):
        self.rollbacks += 1
        self.in_transaction = False
        if self.rollback_error is not None:
            raise self.rollback_error

    def close(self):
        self.closes += 1
        if self.close_error is not None:
            raise self.close_error


def test_connection_setup_and_session_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend = object.__new__(SQLiteTenantMigrationLockBackend)
    backend._path = tmp_path / "locks.sqlite3"

    conn = FakeConnection()
    monkeypatch.setattr(sqlite_module, "connect_sqlite", lambda *args, **kwargs: conn)
    assert backend._connect(write=True) is conn
    assert conn.executions[-1] == "BEGIN IMMEDIATE"

    conn = FakeConnection()
    monkeypatch.setattr(sqlite_module, "connect_sqlite", lambda *args, **kwargs: conn)
    assert backend._connect(write=False).executions[-1] == "BEGIN"

    conn = FakeConnection()
    conn.execute_error = RuntimeError("pragma failed")
    monkeypatch.setattr(sqlite_module, "connect_sqlite", lambda *args, **kwargs: conn)
    with pytest.raises(RuntimeError, match="pragma failed"):
        backend._connect()
    assert conn.closes == 1

    conn = FakeConnection()
    conn.execute_error = RuntimeError("pragma failed")
    conn.close_error = RuntimeError("close failed")
    monkeypatch.setattr(sqlite_module, "connect_sqlite", lambda *args, **kwargs: conn)
    with pytest.raises(RuntimeError, match="pragma failed") as raised:
        backend._connect()
    assert any("close also failed" in note for note in raised.value.__notes__)

    conn = FakeConnection()
    monkeypatch.setattr(backend, "_connect", lambda **_: conn)
    with backend._session(write=True) as active:
        assert active is conn
    assert (conn.commits, conn.rollbacks, conn.closes) == (1, 0, 1)

    conn = FakeConnection()
    monkeypatch.setattr(backend, "_connect", lambda **_: conn)
    with pytest.raises(RuntimeError, match="body failed"):
        with backend._session():
            raise RuntimeError("body failed")
    assert (conn.commits, conn.rollbacks, conn.closes) == (0, 1, 1)

    conn = FakeConnection()
    conn.rollback_error = RuntimeError("rollback failed")
    conn.close_error = RuntimeError("close failed")
    monkeypatch.setattr(backend, "_connect", lambda **_: conn)
    with pytest.raises(RuntimeError, match="body failed") as raised:
        with backend._session():
            raise RuntimeError("body failed")
    assert any("rollback also failed" in note for note in raised.value.__notes__)
    assert any("close also failed" in note for note in raised.value.__notes__)

    conn = FakeConnection()
    conn.commit_error = RuntimeError("commit failed")
    monkeypatch.setattr(backend, "_connect", lambda **_: conn)
    with pytest.raises(RuntimeError, match="commit failed"):
        with backend._session():
            pass
    assert (conn.commits, conn.rollbacks, conn.closes) == (1, 1, 1)

    conn = FakeConnection()
    conn.commit_error = RuntimeError("commit failed")
    conn.rollback_error = RuntimeError("rollback failed")
    conn.close_error = RuntimeError("close failed")
    monkeypatch.setattr(backend, "_connect", lambda **_: conn)
    with pytest.raises(RuntimeError, match="commit failed") as raised:
        with backend._session():
            pass
    assert any("rollback also failed" in note for note in raised.value.__notes__)
    assert any("close also failed" in note for note in raised.value.__notes__)

    conn = FakeConnection()
    conn.close_error = RuntimeError("close failed")
    monkeypatch.setattr(backend, "_connect", lambda **_: conn)
    with pytest.raises(RuntimeError, match="close failed"):
        with backend._session():
            pass
