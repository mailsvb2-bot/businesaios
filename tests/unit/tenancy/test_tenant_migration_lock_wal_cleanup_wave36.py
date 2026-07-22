from __future__ import annotations

from pathlib import Path

import pytest

import tenancy.tenant_migration_lock_sqlite as module
from runtime.platform.event_store.sqlite_platform import SQLiteOperationalError
from tenancy.tenant_migration_lock_sqlite import SQLiteTenantMigrationLockBackend


class _Cursor:
    def fetchone(self):
        return None


class _FailingWalConnection:
    def __init__(self, primary: SQLiteOperationalError) -> None:
        self.primary = primary
        self.row_factory = None
        self.closes = 0

    def execute(self, sql: str):
        if sql.startswith("PRAGMA busy_timeout="):
            return _Cursor()
        if sql == "PRAGMA journal_mode=WAL":
            raise self.primary
        raise AssertionError(f"unexpected SQL: {sql}")

    def close(self) -> None:
        self.closes += 1
        raise RuntimeError("close failed")


def _backend(tmp_path: Path) -> SQLiteTenantMigrationLockBackend:
    backend = object.__new__(SQLiteTenantMigrationLockBackend)
    backend._path = tmp_path / "locks.sqlite3"
    return backend


def test_wal_bootstrap_propagates_connect_failure_without_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _backend(tmp_path)
    failure = SQLiteOperationalError("disk I/O error")

    def fail_connect(*args, **kwargs):
        raise failure

    monkeypatch.setattr(module, "connect_sqlite", fail_connect)
    monkeypatch.setattr(module, "monotonic", lambda: 0.0)

    with pytest.raises(SQLiteOperationalError, match="disk I/O") as raised:
        backend._ensure_wal_mode()

    assert raised.value is failure


def test_wal_bootstrap_preserves_non_retryable_error_when_close_also_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _backend(tmp_path)
    primary = SQLiteOperationalError("disk I/O error")
    connection = _FailingWalConnection(primary)
    monkeypatch.setattr(
        module,
        "connect_sqlite",
        lambda *args, **kwargs: connection,
    )
    monkeypatch.setattr(module, "monotonic", lambda: 0.0)

    with pytest.raises(SQLiteOperationalError, match="disk I/O") as raised:
        backend._ensure_wal_mode()

    assert raised.value is primary
    assert connection.closes == 1
    assert any("WAL close also failed" in note for note in primary.__notes__)
