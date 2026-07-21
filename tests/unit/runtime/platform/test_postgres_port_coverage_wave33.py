from __future__ import annotations

import sys

import pytest

from runtime.platform.postgres_port import PostgresPort


class FakeCursor:
    def __init__(self, *, execute_error: Exception | None = None, one=None, all_rows=None):
        self.execute_error = execute_error
        self.one = one
        self.all_rows = [] if all_rows is None else all_rows
        self.executions: list[tuple[str, object]] = []
        self.entered = 0
        self.exited = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exited += 1

    def execute(self, sql, params=None):
        self.executions.append((sql, params))
        if self.execute_error is not None:
            raise self.execute_error

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.all_rows


class FakeConnection:
    def __init__(self, cursors: list[FakeCursor] | None = None):
        self.cursors = list(cursors or [])
        self.created: list[FakeCursor] = []
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0
        self.fail_commit = False
        self.fail_rollback = False
        self.fail_close = False

    def cursor(self):
        cursor = self.cursors.pop(0) if self.cursors else FakeCursor()
        self.created.append(cursor)
        return cursor

    def commit(self):
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("commit failed")

    def rollback(self):
        self.rollbacks += 1
        if self.fail_rollback:
            raise RuntimeError("rollback failed")

    def close(self):
        self.closes += 1
        if self.fail_close:
            raise RuntimeError("close failed")


class FakePsycopg:
    def __init__(self, conn: FakeConnection):
        self.conn = conn
        self.calls: list[tuple[str, bool]] = []

    def connect(self, dsn: str, *, autocommit: bool):
        self.calls.append((dsn, autocommit))
        return self.conn


def install(monkeypatch: pytest.MonkeyPatch, conn: FakeConnection) -> FakePsycopg:
    module = FakePsycopg(conn)
    monkeypatch.setitem(sys.modules, "psycopg", module)
    return module


def test_dsn_validation_rejects_missing_and_blank() -> None:
    with pytest.raises(ValueError, match="POSTGRES_DSN is empty"):
        PostgresPort("")
    with pytest.raises(ValueError, match="POSTGRES_DSN is empty"):
        PostgresPort("   ")


def test_enter_sets_application_name_and_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    cursor = FakeCursor()
    conn = FakeConnection([cursor])
    driver = install(monkeypatch, conn)
    port = PostgresPort("postgres://db", application_name="behavior-graph")
    assert port.__enter__() is port
    assert driver.calls == [("postgres://db", False)]
    assert cursor.executions == [("SELECT set_config('application_name', %s, false);", ("behavior-graph",))]
    assert conn.commits == 1
    assert port._psycopg is driver


def test_enter_tolerates_only_set_config_compatibility_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tolerated = FakeConnection([FakeCursor(execute_error=RuntimeError("set_config unavailable"))])
    install(monkeypatch, tolerated)
    port = PostgresPort("postgres://db")
    assert port.__enter__() is port
    assert tolerated.rollbacks == 1
    assert tolerated.commits == 0

    rejected = FakeConnection([FakeCursor(execute_error=RuntimeError("permission denied"))])
    install(monkeypatch, rejected)
    with pytest.raises(RuntimeError, match="permission denied"):
        PostgresPort("postgres://db").__enter__()
    assert rejected.rollbacks == 1

    rollback_fails = FakeConnection([FakeCursor(execute_error=RuntimeError("permission denied"))])
    rollback_fails.fail_rollback = True
    install(monkeypatch, rollback_fails)
    with pytest.raises(RuntimeError, match="permission denied") as raised:
        PostgresPort("postgres://db").__enter__()
    assert any("rollback also failed" in note for note in raised.value.__notes__)


def test_exit_commits_or_rolls_back_closes_and_is_idempotent() -> None:
    unused = PostgresPort("postgres://db")
    unused.__exit__(None, None, None)

    conn = FakeConnection()
    port = PostgresPort("postgres://db")
    port._conn = conn
    port.__exit__(None, None, None)
    assert (conn.commits, conn.rollbacks, conn.closes) == (1, 0, 1)
    assert port._conn is None
    port.__exit__(None, None, None)

    conn = FakeConnection()
    port._conn = conn
    port.__exit__(RuntimeError, RuntimeError("boom"), None)
    assert (conn.commits, conn.rollbacks, conn.closes) == (0, 1, 1)
    assert port._conn is None

    conn = FakeConnection()
    conn.fail_close = True
    port._conn = conn
    with pytest.raises(RuntimeError, match="close failed"):
        port.__exit__(None, None, None)
    assert port._conn is None


def test_explicit_transaction_preserves_original_failures() -> None:
    conn = FakeConnection()
    port = PostgresPort("postgres://db")
    port._conn = conn
    with port.transaction() as active:
        assert active is port
    assert conn.commits == 1

    with pytest.raises(RuntimeError, match="body failed"):
        with port.transaction():
            raise RuntimeError("body failed")
    assert conn.rollbacks == 1

    conn.fail_rollback = True
    with pytest.raises(RuntimeError, match="body failed") as raised:
        with port.transaction():
            raise RuntimeError("body failed")
    assert any("rollback also failed" in note for note in raised.value.__notes__)

    conn.fail_rollback = False
    conn.fail_commit = True
    with pytest.raises(RuntimeError, match="commit failed"):
        with port.transaction():
            pass


def test_execute_fetch_ping_commit_and_rollback_delegate_to_connection() -> None:
    execute_cursor = FakeCursor()
    one_cursor = FakeCursor(one=(1,))
    all_cursor = FakeCursor(all_rows=[(1,), (2,)])
    ping_cursor = FakeCursor(one=(1,))
    failing_ping = FakeCursor(execute_error=RuntimeError("down"))
    conn = FakeConnection([execute_cursor, one_cursor, all_cursor, ping_cursor, failing_ping])
    port = PostgresPort("postgres://db")
    port._conn = conn

    port.execute("UPDATE x SET y=%s", (1,))
    assert execute_cursor.executions == [("UPDATE x SET y=%s", (1,))]
    assert port.fetchone("SELECT one") == (1,)
    assert port.fetchall("SELECT all") == [(1,), (2,)]
    assert port.ping() is True
    assert port.ping() is False
    port.commit()
    port.rollback()
    assert conn.commits == 1
    assert conn.rollbacks == 1


def test_enter_and_exit_cleanup_failures_never_mask_primary_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rejected = FakeConnection([FakeCursor(execute_error=RuntimeError("permission denied"))])
    rejected.fail_rollback = True
    rejected.fail_close = True
    install(monkeypatch, rejected)
    port = PostgresPort("postgres://db")
    with pytest.raises(RuntimeError, match="permission denied") as raised:
        port.__enter__()
    assert port._conn is None
    assert any("rollback also failed" in note for note in raised.value.__notes__)
    assert any("close also failed" in note for note in raised.value.__notes_)

    conn = FakeConnection()
    conn.fail_commit = True
    port._conn = conn
    with pytest.raises(RuntimeError, match="commit failed"):
        port.__exit__(None, None, None)
    assert (conn.commits, conn.rollbacks, conn.closes) == (1, 1, 1)
    assert port._conn is None

    conn = FakeConnection()
    conn.fail_commit = True
    conn.fail_rollback = True
    conn.fail_close = True
    port._conn = conn
    with pytest.raises(RuntimeError, match="commit failed") as raised:
        port.__exit__(None, None, None)
    assert any("rollback also failed" in note for note in raised.value.__notes_)
    assert any("close also failed" in note for note in raised.value.__notes_)

    conn = FakeConnection()
    conn.fail_rollback = True
    conn.fail_close = True
    body_error = RuntimeError("body failed")
    port._conn = conn
    port.__exit__(RuntimeError, body_error, None)
    assert any("rollback also failed" in note for note in body_error.__notes_)
    assert any("close also failed" in note for note in body_error.__notes__)

    conn = FakeConnection()
    conn.fail_rollback = True
    port._conn = conn
    with pytest.raises(RuntimeError, match="rollback failed"):
        port.__exit__(RuntimeError, None, None)


def test_transaction_commit_and_rollback_failures_preserve_commit_error() -> None:
    conn = FakeConnection()
    conn.fail_commit = True
    conn.fail_rollback = True
    port = PostgresPort("postgres://db")
    port._conn = conn
    with pytest.raises(RuntimeError, match="commit failed") as raised:
        with port.transaction():
            pass
    assert conn.rollbacks == 1
    assert any("rollback also failed" in note for note in raised.value.__notes__)
