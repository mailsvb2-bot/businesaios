from __future__ import annotations

import sqlite3

import pytest

from runtime.queue import _sqlite_job_store_db as dbmod


class _FakeDB:
    def __init__(self, failures: list[Exception]) -> None:
        self.failures = list(failures)
        self.calls = 0

    def execute(self, _sql: str):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        return object()


def test_begin_immediate_retries_transient_database_locked(monkeypatch) -> None:
    db = _FakeDB([
        sqlite3.OperationalError("database is locked"),
        sqlite3.OperationalError("database is locked"),
    ])
    sleeps = []
    monkeypatch.setattr(dbmod.time, "sleep", lambda value: sleeps.append(value))

    dbmod._begin_immediate_with_retry(db, attempts=4)

    assert db.calls == 3
    assert sleeps == [0.01, 0.02]


def test_begin_immediate_exhausted_lock_still_fails(monkeypatch) -> None:
    db = _FakeDB([sqlite3.OperationalError("database is locked")] * 4)
    monkeypatch.setattr(dbmod.time, "sleep", lambda _value: None)

    with pytest.raises(sqlite3.OperationalError, match="database is locked"):
        dbmod._begin_immediate_with_retry(db, attempts=4)

    assert db.calls == 4


def test_begin_immediate_does_not_retry_other_operational_errors(monkeypatch) -> None:
    db = _FakeDB([sqlite3.OperationalError("disk I/O error")])
    sleeps = []
    monkeypatch.setattr(dbmod.time, "sleep", lambda value: sleeps.append(value))

    with pytest.raises(sqlite3.OperationalError, match="disk I/O error"):
        dbmod._begin_immediate_with_retry(db, attempts=4)

    assert db.calls == 1
    assert sleeps == []
