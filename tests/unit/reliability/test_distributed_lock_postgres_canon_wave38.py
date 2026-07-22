from __future__ import annotations

from collections import deque
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
from threading import Barrier, Lock, Thread

import pytest

import reliability.distributed_lock_postgres as module
from reliability.distributed_lock_contracts import LockLease
from reliability.distributed_lock_postgres import PostgresDistributedLockBackend

NOW = datetime(2026, 7, 22, 12, tzinfo=UTC)


def lease(owner="owner-a", token=1, acquired=NOW, expires=NOW + timedelta(seconds=60)):
    return LockLease("tenant-a", "orders", owner, token, acquired, expires)


def row(value):
    return {
        "tenant_id": value.tenant_id,
        "resource": value.resource,
        "owner_id": value.owner_id,
        "fencing_token": value.fencing_token,
        "acquired_at": value.acquired_at,
        "expires_at": value.expires_at,
    }


class Session(AbstractContextManager):
    def __init__(self, fetches=(), fail_execute=None, fail_rollback=None):
        self.fetches = deque(fetches)
        self.fail_execute = fail_execute
        self.fail_rollback = fail_rollback
        self.execs = []
        self.fetch_sql = []
        self.commits = self.rollbacks = self.enters = self.exits = 0

    def __enter__(self):
        self.enters += 1
        return self

    def __exit__(self, *_):
        self.exits += 1

    def execute(self, sql, params=None):
        self.execs.append((sql, params))
        if self.fail_execute == len(self.execs):
            raise RuntimeError("execute failed")

    def fetchone(self, sql, params=None):
        self.fetch_sql.append((sql, params))
        if not self.fetches:
            raise AssertionError(f"unexpected fetch: {sql}")
        value = self.fetches.popleft()
        if isinstance(value, BaseException):
            raise value
        return value

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1
        if self.fail_rollback:
            raise self.fail_rollback


class Factory:
    def __init__(self, *sessions):
        self.sessions = deque(sessions)
        self.opens = 0

    def open(self):
        self.opens += 1
        return self.sessions.popleft()


def backend_with(session):
    backend = PostgresDistributedLockBackend(dsn="postgresql://test")
    backend._sessions = Factory(session)
    backend._schema_ready = True
    return backend


class ReadyLock:
    def __init__(self, backend):
        self.backend = backend

    def __enter__(self):
        self.backend._schema_ready = True

    def __exit__(self, *_):
        return None


def test_constructor_ping_schema_and_rollback_contracts():
    backend = PostgresDistributedLockBackend(
        dsn="postgresql://test",
        application_name="locks-test",
        statement_timeout_ms=12,
        lock_timeout_ms=7,
        table_prefix="tenant_lock",
    )
    assert backend._locks_table == "tenant_lock_distributed_locks"
    assert backend._tokens_table == "tenant_lock_lock_tokens"
    assert backend._sessions.application_name == "locks-test"
    assert backend._sessions.statement_timeout_ms == 12
    assert backend._sessions.lock_timeout_ms == 7
    with pytest.raises(ValueError, match="unsafe sql identifier"):
        PostgresDistributedLockBackend(dsn="x", table_prefix="bad-prefix")

    good = Session([{"ok": 1}])
    backend._sessions = Factory(good)
    assert backend.ping()
    for value in (None, {"ok": 0}, RuntimeError("offline")):
        session = Session([value])
        backend._sessions = Factory(session)
        assert not backend.ping()

    schema = Session()
    backend._sessions = Factory(schema)
    backend._schema_ready = False
    backend._ensure_schema()
    backend._ensure_schema()
    assert len(schema.execs) == 3 and schema.commits == 1
    failing = Session(fail_execute=2)
    backend = PostgresDistributedLockBackend(dsn="x")
    backend._sessions = Factory(failing)
    with pytest.raises(RuntimeError, match="execute failed"):
        backend._ensure_schema()
    assert failing.rollbacks == 1 and not backend._schema_ready
    backend._schema_lock = ReadyLock(backend)
    backend._ensure_schema()

    rollback = Session(fail_rollback=RuntimeError("rollback failed"))
    primary = RuntimeError("primary")
    backend._rollback_preserving(rollback, primary)
    assert primary.__notes__ == [
        "distributed lock rollback also failed: rollback failed"
    ]


def test_token_helpers_and_fail_closed_edges():
    session = Session([{"last_token": 4}, {"last_token": 5}])
    backend = backend_with(session)
    assert backend._lock_token_row_in_tx(
        session=session, tenant_id="tenant-a", resource="orders", now=NOW
    ) == 4
    assert backend._next_token_in_tx(
        session=session, tenant_id="tenant-a", resource="orders", now=NOW
    ) == 5
    assert backend._ensure_token_floor_in_tx(
        session=session,
        tenant_id="tenant-a",
        resource="orders",
        minimum_token=4,
        current_token=5,
        now=NOW,
    ) == (5, False)
    restored = Session([{"last_token": 7}])
    assert backend._ensure_token_floor_in_tx(
        session=restored,
        tenant_id="tenant-a",
        resource="orders",
        minimum_token=7,
        current_token=0,
        now=NOW,
    ) == (7, True)
    for method, fetches, match, kwargs in (
        (backend._lock_token_row_in_tx, [None], "lock fencing", {}),
        (backend._next_token_in_tx, [None], "allocate fencing", {}),
        (
            backend._ensure_token_floor_in_tx,
            [None],
            "restore fencing",
            {"minimum_token": 7, "current_token": 0},
        ),
        (
            backend._ensure_token_floor_in_tx,
            [{"last_token": 6}],
            "restoration regressed",
            {"minimum_token": 7, "current_token": 0},
        ),
    ):
        with pytest.raises(RuntimeError, match=match):
            method(
                session=Session(fetches),
                tenant_id="tenant-a",
                resource="orders",
                now=NOW,
                **kwargs,
            )


def test_acquire_validation_and_state_transitions():
    backend = PostgresDistributedLockBackend(dsn="x")
    for kwargs in (
        {"tenant_id": "default", "resource": "r", "owner_id": "o"},
        {"tenant_id": "tenant-a", "resource": "", "owner_id": "o"},
        {"tenant_id": "tenant-a", "resource": "r", "owner_id": ""},
        {
            "tenant_id": "tenant-a",
            "resource": "r",
            "owner_id": "o",
            "ttl_seconds": 0,
        },
        {
            "tenant_id": "tenant-a",
            "resource": "r",
            "owner_id": "o",
            "now": datetime(2026, 1, 1),
        },
    ):
        with pytest.raises(ValueError):
            backend.acquire(**kwargs)

    free = Session([{"last_token": 0}, None, {"last_token": 1}])
    acquired = backend_with(free).acquire(
        tenant_id=" tenant-a ",
        resource=" orders ",
        owner_id=" worker-a ",
        ttl_seconds=30,
        now=NOW,
    )
    assert acquired == lease(owner="worker-a", expires=NOW + timedelta(seconds=30))
    assert free.commits == 1 and free.rollbacks == 0

    live = Session([{"last_token": 1}, row(lease(expires=NOW + timedelta(seconds=1)))])
    assert backend_with(live).acquire(
        tenant_id="tenant-a", resource="orders", owner_id="owner-b", now=NOW
    ) is None
    assert live.rollbacks == 1

    repaired_live = Session(
        [{"last_token": 0}, row(lease(token=5)), {"last_token": 5}]
    )
    assert backend_with(repaired_live).acquire(
        tenant_id="tenant-a", resource="orders", owner_id="owner-b", now=NOW
    ) is None
    assert repaired_live.commits == 1

    expired = lease(
        token=5,
        acquired=NOW - timedelta(seconds=60),
        expires=NOW - timedelta(seconds=1),
    )
    replacement = Session(
        [{"last_token": 0}, row(expired), {"last_token": 5}, {"last_token": 6}]
    )
    result = backend_with(replacement).acquire(
        tenant_id="tenant-a", resource="orders", owner_id="owner-b", now=NOW
    )
    assert result and result.fencing_token == 6 and result.owner_id == "owner-b"

    broken = Session([None])
    with pytest.raises(RuntimeError, match="failed to lock"):
        backend_with(broken).acquire(
            tenant_id="tenant-a", resource="orders", owner_id="owner-a", now=NOW
        )
    assert broken.rollbacks == 1


class Store:
    def __init__(self):
        self.meta = Lock()
        self.resource_locks = {}
        self.tokens = {}
        self.locks = {}
        self.old_barrier = Barrier(2)

    def session(self):
        return ConcurrentSession(self)


class ConcurrentFactory:
    def __init__(self, store):
        self.store = store

    def open(self):
        return self.store.session()


class ConcurrentSession(AbstractContextManager):
    def __init__(self, store):
        self.store = store
        self.held = []
        self.key = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._release()

    def _resource_lock(self, key):
        with self.store.meta:
            return self.store.resource_locks.setdefault(key, Lock())

    def _hold(self, key):
        if self.key == key:
            return
        lock = self._resource_lock(key)
        lock.acquire()
        self.held.append(lock)
        self.key = key

    def execute(self, sql, params=None):
        values = tuple(params or ())
        normalized = " ".join(sql.split())
        if "lock_tokens" in normalized and "DO NOTHING" in normalized:
            key = (str(values[0]), str(values[1]))
            with self.store.meta:
                self.store.tokens.setdefault(key, 0)
            return
        if "distributed_locks" in normalized and normalized.startswith("INSERT"):
            key = (str(values[0]), str(values[1]))
            self.store.locks[key] = {
                "tenant_id": values[0],
                "resource": values[1],
                "owner_id": values[2],
                "fencing_token": values[3],
                "acquired_at": values[4],
                "expires_at": values[5],
            }
            return
        raise AssertionError(normalized)

    def fetchone(self, sql, params=None):
        values = tuple(params or ())
        normalized = " ".join(sql.split())
        if normalized.startswith("SELECT last_token"):
            key = (str(values[0]), str(values[1]))
            self._hold(key)
            return {"last_token": self.store.tokens[key]}
        if normalized.startswith("UPDATE") and "lock_tokens" in normalized:
            key = (str(values[1]), str(values[2]))
            self.store.tokens[key] += 1
            return {"last_token": self.store.tokens[key]}
        if "distributed_locks" in normalized and "FOR UPDATE" in normalized:
            key = (str(values[0]), str(values[1]))
            if self.key != key:
                self.store.old_barrier.wait(timeout=5)
            current = self.store.locks.get(key)
            return None if current is None else dict(current)
        if normalized.startswith("INSERT") and "lock_tokens" in normalized:
            key = (str(values[0]), str(values[1]))
            self._hold(key)
            self.store.tokens[key] = self.store.tokens.get(key, 0) + 1
            return {"last_token": self.store.tokens[key]}
        raise AssertionError(normalized)

    def commit(self):
        self._release()

    def rollback(self):
        self._release()

    def _release(self):
        while self.held:
            self.held.pop().release()
        self.key = None


def test_absent_row_race_has_one_winner_and_one_token():
    store = Store()
    backends = [PostgresDistributedLockBackend(dsn="x") for _ in range(2)]
    for backend in backends:
        backend._sessions = ConcurrentFactory(store)
        backend._schema_ready = True
    start = Barrier(3)
    results = []
    errors = []

    def run(backend, owner):
        try:
            start.wait(timeout=5)
            results.append(
                backend.acquire(
                    tenant_id="tenant-a",
                    resource="orders",
                    owner_id=owner,
                    now=NOW,
                )
            )
        except BaseException as exc:
            errors.append(exc)

    threads = [Thread(target=run, args=(backends[i], f"owner-{i}")) for i in range(2)]
    for thread in threads:
        thread.start()
    start.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=10)
    assert not errors
    assert sum(item is not None for item in results) == 1
    assert sum(item is None for item in results) == 1
    winner = next(item for item in results if item is not None)
    assert winner.fencing_token == store.tokens[("tenant-a", "orders")] == 1
    assert store.locks[("tenant-a", "orders")]["owner_id"] == winner.owner_id


def test_renew_release_and_get_contracts(monkeypatch):
    backend = PostgresDistributedLockBackend(dsn="x")
    with pytest.raises(ValueError, match="fencing_token"):
        backend.renew(lease=lease(token=0), now=NOW)
    with pytest.raises(ValueError, match="ttl_seconds"):
        backend.renew(lease=lease(), ttl_seconds=0, now=NOW)
    with pytest.raises(ValueError, match="timezone-aware"):
        backend.renew(lease=lease(), now=datetime(2026, 1, 1))

    for current, message in (
        (None, "no longer exists"),
        (row(lease(owner="other")), "ownership mismatch"),
        (row(lease(token=2)), "fencing token mismatch"),
        (
            row(
                lease(
                    acquired=NOW - timedelta(seconds=60),
                    expires=NOW,
                )
            ),
            "expired",
        ),
    ):
        session = Session([current])
        with pytest.raises(PermissionError, match=message):
            backend_with(session).renew(lease=lease(), now=NOW)
        assert session.rollbacks == 1

    server_acquired = NOW - timedelta(minutes=5)
    current = lease(acquired=server_acquired)
    success = Session([row(current)])
    renewed = backend_with(success).renew(
        lease=lease(acquired=NOW - timedelta(minutes=1)),
        ttl_seconds=90,
        now=NOW,
    )
    assert renewed.acquired_at == server_acquired
    assert renewed.expires_at == NOW + timedelta(seconds=90)
    assert success.commits == 1

    failed = Session([row(current)], fail_execute=1)
    with pytest.raises(RuntimeError, match="execute failed"):
        backend_with(failed).renew(lease=current, now=NOW)
    assert failed.rollbacks == 1

    with pytest.raises(ValueError):
        backend.release(lease=lease(token=0))
    released = Session()
    backend_with(released).release(lease=lease())
    assert released.commits == 1
    release_failed = Session(fail_execute=1)
    with pytest.raises(RuntimeError, match="execute failed"):
        backend_with(release_failed).release(lease=lease())
    assert release_failed.rollbacks == 1

    for tenant, resource in (("default", "orders"), ("tenant-a", "")):
        with pytest.raises(ValueError):
            backend.get(tenant_id=tenant, resource=resource)
    monkeypatch.setattr(module, "utc_now", lambda: NOW)
    assert backend_with(Session([None])).get(
        tenant_id="tenant-a", resource="orders"
    ) is None
    assert backend_with(Session([row(lease())])).get(
        tenant_id="tenant-a", resource="orders"
    ) == lease()
    expired = lease(
        acquired=NOW - timedelta(seconds=60),
        expires=NOW - timedelta(seconds=1),
    )
    cleanup = Session([row(expired)])
    assert backend_with(cleanup).get(
        tenant_id="tenant-a", resource="orders"
    ) is None
    assert cleanup.commits == 1
    cleanup_failed = Session([row(expired)], fail_execute=1)
    assert backend_with(cleanup_failed).get(
        tenant_id="tenant-a", resource="orders"
    ) is None
    assert cleanup_failed.rollbacks == 1
