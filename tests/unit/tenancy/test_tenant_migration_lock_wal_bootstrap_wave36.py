from __future__ import annotations

from datetime import UTC, datetime
from multiprocessing import get_context
from pathlib import Path

import pytest

import tenancy.tenant_migration_lock_sqlite as module
from runtime.platform.event_store.sqlite_platform import SQLiteOperationalError
from tenancy.tenant_migration_lock_sqlite import SQLiteTenantMigrationLockBackend


NOW = datetime(2026, 7, 22, 8, 0, tzinfo=UTC)


def _construct_and_acquire(path: str, owner: str, gate, results) -> None:
    gate.wait(15)
    try:
        backend = SQLiteTenantMigrationLockBackend(path)
        lock = backend.acquire(
            tenant_id="tenant-a",
            operation_id="migration",
            owner_id=owner,
            ttl_seconds=60,
            now=NOW,
        )
    except BaseException as exc:
        results.put(("error", type(exc).__name__, str(exc)))
        return
    results.put(
        (
            "ok",
            None if lock is None else (lock.owner_id, lock.fencing_token),
        )
    )


class _Cursor:
    def __init__(self, row=None) -> None:
        self._row = row

    def fetchone(self):
        return self._row


class _WalConnection:
    def __init__(self, outcome, *, close_error: BaseException | None = None) -> None:
        self.outcome = outcome
        self.close_error = close_error
        self.row_factory = None
        self.executions: list[str] = []
        self.closes = 0

    def execute(self, sql: str):
        self.executions.append(sql)
        if sql.startswith("PRAGMA busy_timeout="):
            return _Cursor()
        if sql == "PRAGMA journal_mode=WAL":
            if isinstance(self.outcome, BaseException):
                raise self.outcome
            return _Cursor(self.outcome)
        raise AssertionError(f"unexpected SQL: {sql}")

    def close(self) -> None:
        self.closes += 1
        if self.close_error is not None:
            raise self.close_error


class _SessionConnection:
    def __init__(self) -> None:
        self.row_factory = None
        self.executions: list[str] = []
        self.closes = 0

    def execute(self, sql: str):
        self.executions.append(sql)
        return _Cursor()

    def close(self) -> None:
        self.closes += 1


def _uninitialized_backend(tmp_path: Path) -> SQLiteTenantMigrationLockBackend:
    backend = object.__new__(SQLiteTenantMigrationLockBackend)
    backend._path = tmp_path / "locks.sqlite3"
    return backend


def test_two_processes_construct_and_serialize_acquire(tmp_path: Path) -> None:
    context = get_context("spawn")
    gate = context.Barrier(3)
    results = context.Queue()
    path = str(tmp_path / "locks.sqlite3")
    processes = [
        context.Process(
            target=_construct_and_acquire,
            args=(path, owner, gate, results),
        )
        for owner in ("process-a", "process-b")
    ]
    for process in processes:
        process.start()
    gate.wait(timeout=15)
    for process in processes:
        process.join(timeout=30)
        assert process.exitcode == 0

    values = [results.get(timeout=5), results.get(timeout=5)]
    assert all(value[0] == "ok" for value in values), values
    locks = [value[1] for value in values]
    assert sum(value is not None for value in locks) == 1
    assert sum(value is None for value in locks) == 1
    assert next(value for value in locks if value is not None)[1] == 1


def test_wal_bootstrap_retries_busy_connection_then_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _uninitialized_backend(tmp_path)
    success = _WalConnection(("wal",))
    calls = 0

    def connect(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise SQLiteOperationalError("database is busy")
        return success

    times = iter((0.0, 0.0))
    sleeps: list[float] = []
    monkeypatch.setattr(module, "connect_sqlite", connect)
    monkeypatch.setattr(module, "monotonic", lambda: next(times))
    monkeypatch.setattr(module, "sleep", sleeps.append)

    backend._ensure_wal_mode()

    assert calls == 2
    assert sleeps == [module._WAL_BOOTSTRAP_RETRY_SECONDS]
    assert success.executions[0].startswith("PRAGMA busy_timeout=")
    assert success.executions[1] == "PRAGMA journal_mode=WAL"
    assert success.closes == 1


def test_wal_bootstrap_retries_locked_pragma_and_closes_each_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _uninitialized_backend(tmp_path)
    locked = _WalConnection(SQLiteOperationalError("database is locked"))
    success = _WalConnection(("WAL",))
    connections = iter((locked, success))
    times = iter((0.0, 0.0))
    sleeps: list[float] = []
    monkeypatch.setattr(module, "connect_sqlite", lambda *args, **kwargs: next(connections))
    monkeypatch.setattr(module, "monotonic", lambda: next(times))
    monkeypatch.setattr(module, "sleep", sleeps.append)

    backend._ensure_wal_mode()

    assert (locked.closes, success.closes) == (1, 1)
    assert sleeps == [module._WAL_BOOTSTRAP_RETRY_SECONDS]


def test_wal_bootstrap_times_out_and_preserves_close_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _uninitialized_backend(tmp_path)
    locked = SQLiteOperationalError("database is locked")
    connection = _WalConnection(locked, close_error=RuntimeError("close failed"))
    times = iter((0.0, module._WAL_BOOTSTRAP_TIMEOUT_SECONDS + 1.0))
    monkeypatch.setattr(module, "connect_sqlite", lambda *args, **kwargs: connection)
    monkeypatch.setattr(module, "monotonic", lambda: next(times))

    with pytest.raises(TimeoutError, match="WAL bootstrap timed out") as raised:
        backend._ensure_wal_mode()

    assert raised.value.__cause__ is locked
    assert any("close also failed" in note for note in locked.__notes__)
    assert connection.closes == 1


def test_wal_bootstrap_rejects_non_busy_error_and_non_wal_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _uninitialized_backend(tmp_path)
    failure = _WalConnection(SQLiteOperationalError("disk I/O error"))
    monkeypatch.setattr(module, "connect_sqlite", lambda *args, **kwargs: failure)
    monkeypatch.setattr(module, "monotonic", lambda: 0.0)
    with pytest.raises(SQLiteOperationalError, match="disk I/O"):
        backend._ensure_wal_mode()
    assert failure.closes == 1

    wrong_mode = _WalConnection(None)
    monkeypatch.setattr(module, "connect_sqlite", lambda *args, **kwargs: wrong_mode)
    with pytest.raises(RuntimeError, match="did not enable WAL"):
        backend._ensure_wal_mode()
    assert wrong_mode.closes == 1


def test_wal_bootstrap_success_close_failure_is_not_hidden(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _uninitialized_backend(tmp_path)
    connection = _WalConnection(("wal",), close_error=RuntimeError("close failed"))
    monkeypatch.setattr(module, "connect_sqlite", lambda *args, **kwargs: connection)
    monkeypatch.setattr(module, "monotonic", lambda: 0.0)

    with pytest.raises(RuntimeError, match="close failed"):
        backend._ensure_wal_mode()


def test_regular_connection_configures_busy_timeout_without_reapplying_wal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _uninitialized_backend(tmp_path)
    connection = _SessionConnection()
    monkeypatch.setattr(module, "connect_sqlite", lambda *args, **kwargs: connection)

    assert backend._connect(write=True) is connection
    assert connection.executions == [
        f"PRAGMA busy_timeout={module._SQLITE_BUSY_TIMEOUT_MS}",
        "PRAGMA synchronous=NORMAL",
        "BEGIN IMMEDIATE",
    ]
    assert "PRAGMA journal_mode=WAL" not in connection.executions
