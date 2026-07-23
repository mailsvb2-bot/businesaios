from __future__ import annotations

import builtins
import sys
import time
from collections import deque
from datetime import UTC, datetime, timedelta
from threading import Barrier, Lock, Thread
from types import SimpleNamespace

import pytest

import reliability.distributed_lock_redis as module
from reliability.distributed_lock_contracts import LockLease
from reliability.distributed_lock_redis import RedisDistributedLockBackend

NOW = datetime(2026, 7, 23, 12, tzinfo=UTC)
READ_AT = datetime(2026, 7, 23, 13, tzinfo=UTC)


def epoch_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def lease(
    *,
    owner: str = "owner-a",
    token: int = 7,
    acquired: datetime = NOW,
    expires: datetime = NOW + timedelta(seconds=60),
) -> LockLease:
    return LockLease("tenant-a", "orders", owner, token, acquired, expires)


class Script:
    def __init__(self, results=()):
        self.results = deque(results)
        self.calls = []

    def __call__(self, *, keys, args):
        self.calls.append((keys, args))
        if not self.results:
            raise AssertionError("unexpected script call")
        result = self.results.popleft()
        if isinstance(result, BaseException):
            raise result
        return result


class Client:
    def __init__(self, scripts=(), *, ping=True, fail_register_at=None, delay=0.0):
        self.scripts = deque(scripts)
        self.ping_result = ping
        self.fail_register_at = fail_register_at
        self.delay = delay
        self.registered = []
        self.register_lock = Lock()

    def register_script(self, source):
        with self.register_lock:
            index = len(self.registered) + 1
            if self.delay:
                time.sleep(self.delay)
            if self.fail_register_at == index:
                raise RuntimeError("register failed")
            if not self.scripts:
                raise AssertionError("unexpected script registration")
            script = self.scripts.popleft()
            self.registered.append((source, script))
            return script

    def ping(self):
        if isinstance(self.ping_result, BaseException):
            raise self.ping_result
        return self.ping_result


def scripts(*, acquire=(), renew=(), read=(), release=()):
    return (
        Script(acquire),
        Script(renew),
        Script(read),
        Script(release),
    )


def registered_backend(*, acquire=(), renew=(), read=(), release=()):
    acquire_script, renew_script, read_script, release_script = scripts(
        acquire=acquire, renew=renew, read=read, release=release
    )
    backend = RedisDistributedLockBackend(client=object())
    backend._scripts_registered = True
    backend._acquire_script = acquire_script
    backend._renew_script = renew_script
    backend._read_script = read_script
    backend._release_script = release_script
    return backend, acquire_script, renew_script, read_script, release_script


def test_constructor_client_import_ping_decode_and_registration_fail_closed(
    monkeypatch,
):
    with pytest.raises(ValueError, match="key_prefix"):
        RedisDistributedLockBackend(client=object(), key_prefix=" ")

    supplied = object()
    backend = RedisDistributedLockBackend(client=supplied, key_prefix=" prefix ")
    assert backend._ensure_client() is supplied
    assert backend._key_prefix == "prefix"
    assert backend._lock_key("t", "r") == "prefix:t:r"
    assert backend._token_key("t", "r") == "prefix:token:t:r"

    missing = RedisDistributedLockBackend()
    with pytest.raises(ValueError, match="redis_url"):
        missing._ensure_client()
    assert not missing.ping()

    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "redis":
            raise ImportError("redis missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    with pytest.raises(RuntimeError, match="requires the `redis` package"):
        RedisDistributedLockBackend(redis_url="redis://localhost")._ensure_client()
    monkeypatch.setattr(builtins, "__import__", real_import)

    created = Client(ping=1)

    class RedisFactory:
        @staticmethod
        def from_url(url, **kwargs):
            assert url == "redis://localhost/3"
            assert kwargs == {"decode_responses": True}
            return created

    monkeypatch.setitem(sys.modules, "redis", SimpleNamespace(Redis=RedisFactory))
    imported = RedisDistributedLockBackend(redis_url=" redis://localhost/3 ")
    assert imported._ensure_client() is created
    assert imported._ensure_client() is created
    assert imported.ping()
    created.ping_result = 0
    assert not imported.ping()
    created.ping_result = RuntimeError("offline")
    assert not imported.ping()

    assert backend._text(b"owner-a") == "owner-a"
    assert backend._text(12) == "12"
    with pytest.raises(RuntimeError, match="missing value"):
        backend._text(None)
    with pytest.raises(RuntimeError, match="not UTF-8"):
        backend._text(b"\xff")
    assert backend._result_values([b"1", 2]) == ("1", "2")
    for value in ("abc", b"abc", 3, None):
        with pytest.raises(RuntimeError, match="invalid result"):
            backend._result_values(value)

    partial_scripts = scripts()
    failing_client = Client(partial_scripts, fail_register_at=4)
    partial = RedisDistributedLockBackend(client=failing_client)
    with pytest.raises(RuntimeError, match="register failed"):
        partial._register_scripts()
    assert not partial._scripts_registered
    for name in ("_acquire_script", "_renew_script", "_read_script", "_release_script"):
        assert not hasattr(partial, name)


def test_script_registration_has_one_thread_safe_owner():
    acquire_script, renew_script, read_script, release_script = scripts()
    client = Client(
        (acquire_script, renew_script, read_script, release_script), delay=0.002
    )
    backend = RedisDistributedLockBackend(client=client)
    start = Barrier(9)
    failures = []

    def register():
        try:
            start.wait(timeout=5)
            backend._register_scripts()
        except BaseException as exc:  # pragma: no cover - diagnostic only
            failures.append(exc)

    threads = [Thread(target=register) for _ in range(8)]
    for thread in threads:
        thread.start()
    start.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=5)

    assert not failures
    assert not any(thread.is_alive() for thread in threads)
    assert len(client.registered) == 4
    assert [source for source, _ in client.registered] == [
        backend._ACQUIRE_SCRIPT,
        backend._RENEW_SCRIPT,
        backend._READ_SCRIPT,
        backend._RELEASE_SCRIPT,
    ]
    assert backend._acquire_script is acquire_script
    assert backend._renew_script is renew_script
    assert backend._read_script is read_script
    assert backend._release_script is release_script
    backend._register_scripts()
    assert len(client.registered) == 4


def test_acquire_validation_denial_binary_success_and_malformed_results():
    invalid = RedisDistributedLockBackend(client=object())
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
            invalid.acquire(**kwargs)
    assert not invalid._scripts_registered

    acquired_ms = epoch_ms(NOW)
    expires_ms = epoch_ms(NOW + timedelta(seconds=30))
    backend, acquire_script, *_ = registered_backend(
        acquire=[
            None,
            [b"7", str(acquired_ms).encode(), str(expires_ms).encode()],
            ["1", "2"],
            "scalar",
            [None, "2", "3"],
            ["0", str(acquired_ms), str(expires_ms)],
        ]
    )
    assert (
        backend.acquire(
            tenant_id="tenant-a", resource="orders", owner_id="owner-a", now=NOW
        )
        is None
    )
    result = backend.acquire(
        tenant_id=" tenant-a ",
        resource=" orders ",
        owner_id=" owner-a ",
        ttl_seconds=30,
        now=NOW,
    )
    assert result == lease(expires=NOW + timedelta(seconds=30))
    assert acquire_script.calls[1] == (
        [
            "businesaios:reliability:lock:tenant-a:orders",
            "businesaios:reliability:lock:token:tenant-a:orders",
        ],
        [
            "tenant-a",
            "orders",
            "owner-a",
            str(acquired_ms),
            str(expires_ms),
            "30000",
        ],
    )
    with pytest.raises(RuntimeError, match="acquire script returned"):
        backend.acquire(
            tenant_id="tenant-a", resource="orders", owner_id="owner-a", now=NOW
        )
    with pytest.raises(RuntimeError, match="invalid result"):
        backend.acquire(
            tenant_id="tenant-a", resource="orders", owner_id="owner-a", now=NOW
        )
    with pytest.raises(RuntimeError, match="missing value"):
        backend.acquire(
            tenant_id="tenant-a", resource="orders", owner_id="owner-a", now=NOW
        )
    with pytest.raises(ValueError, match="fencing_token"):
        backend.acquire(
            tenant_id="tenant-a", resource="orders", owner_id="owner-a", now=NOW
        )


def test_renew_and_release_strict_binary_safe_contracts():
    invalid_backend = RedisDistributedLockBackend(client=object())
    invalid_lease = lease(token=0)
    with pytest.raises(ValueError, match="fencing_token"):
        invalid_backend.renew(lease=invalid_lease)
    with pytest.raises(ValueError, match="fencing_token"):
        invalid_backend.release(lease=invalid_lease)
    with pytest.raises(ValueError, match="ttl_seconds"):
        invalid_backend.renew(lease=lease(), ttl_seconds=0, now=NOW)
    with pytest.raises(ValueError, match="timezone-aware"):
        invalid_backend.renew(lease=lease(), now=datetime(2026, 1, 1))
    assert not invalid_backend._scripts_registered

    acquired_ms = epoch_ms(NOW)
    expires_ms = epoch_ms(NOW + timedelta(seconds=45))
    backend, _, renew_script, _, release_script = registered_backend(
        renew=[
            None,
            [b"MISSING"],
            [b"OWNER_MISMATCH"],
            [b"TOKEN_MISMATCH"],
            ["7", str(acquired_ms)],
            ["8", str(acquired_ms), str(expires_ms)],
            [b"7", str(acquired_ms).encode(), str(expires_ms).encode()],
        ],
        release=[1],
    )
    for match in (
        "no longer exists",
        "no longer exists",
        "ownership mismatch",
        "fencing token mismatch",
    ):
        with pytest.raises(PermissionError, match=match):
            backend.renew(lease=lease(), ttl_seconds=45, now=NOW)
    with pytest.raises(RuntimeError, match="renew script returned"):
        backend.renew(lease=lease(), ttl_seconds=45, now=NOW)
    with pytest.raises(RuntimeError, match="changed the fencing token"):
        backend.renew(lease=lease(), ttl_seconds=45, now=NOW)
    renewed = backend.renew(lease=lease(), ttl_seconds=45, now=NOW)
    assert renewed == lease(expires=NOW + timedelta(seconds=45))
    assert renew_script.calls[-1] == (
        ["businesaios:reliability:lock:tenant-a:orders"],
        ["owner-a", "7", str(expires_ms), "45000"],
    )

    backend.release(lease=lease())
    assert release_script.calls == [
        (
            ["businesaios:reliability:lock:tenant-a:orders"],
            ["owner-a", "7"],
        )
    ]


def test_get_uses_atomic_server_ttl_and_fails_closed_on_corruption(monkeypatch):
    invalid = RedisDistributedLockBackend(client=object())
    for tenant_id, resource in (("default", "orders"), ("tenant-a", "")):
        with pytest.raises(ValueError):
            invalid.get(tenant_id=tenant_id, resource=resource)
    assert not invalid._scripts_registered

    future_ms = epoch_ms(READ_AT + timedelta(hours=2))
    past_ms = epoch_ms(READ_AT - timedelta(seconds=5))
    outputs = [
        None,
        [b"NO_EXPIRY"],
        ["tenant-a", "orders", "owner-a", "7", str(past_ms), "0"],
        ["tenant-a", "orders", "owner-a", "7", str(past_ms), "bad"],
        [b"tenant-a", b"orders", b"owner-a", b"7", str(future_ms).encode(), b"2500"],
        ["tenant-a", "orders", "owner-a", "8", str(past_ms), "1000"],
        ["other", "orders", "owner-a", "7", str(past_ms), "1000"],
        ["tenant-a", "orders", "owner-a", "7", str(past_ms)],
        ["tenant-a", "orders", None, "7", str(past_ms), "1000"],
        ["tenant-a", "orders", b"\xff", "7", str(past_ms), "1000"],
        ["tenant-a", "orders", "owner-a", "bad", str(past_ms), "1000"],
        "scalar",
        ["tenant-a", "orders", "", "7", str(past_ms), "1000"],
        ["tenant-a", "orders", "owner-a", "7", "bad", "1000"],
    ]
    backend, _, _, read_script, _ = registered_backend(read=outputs)
    monkeypatch.setattr(module, "utc_now", lambda: READ_AT)

    assert backend.get(tenant_id="tenant-a", resource="orders") is None
    with pytest.raises(RuntimeError, match="no expiry"):
        backend.get(tenant_id="tenant-a", resource="orders")
    assert backend.get(tenant_id="tenant-a", resource="orders") is None
    with pytest.raises(RuntimeError, match="payload is invalid"):
        backend.get(tenant_id="tenant-a", resource="orders")

    current = backend.get(tenant_id=" tenant-a ", resource=" orders ")
    assert current == lease(
        token=7,
        acquired=READ_AT,
        expires=READ_AT + timedelta(milliseconds=2500),
    )
    older = backend.get(tenant_id="tenant-a", resource="orders")
    assert older == lease(
        token=8,
        acquired=READ_AT - timedelta(seconds=5),
        expires=READ_AT + timedelta(seconds=1),
    )

    with pytest.raises(RuntimeError, match="payload is invalid"):
        backend.get(tenant_id="tenant-a", resource="orders")
    with pytest.raises(RuntimeError, match="read script returned"):
        backend.get(tenant_id="tenant-a", resource="orders")
    with pytest.raises(RuntimeError, match="missing value"):
        backend.get(tenant_id="tenant-a", resource="orders")
    with pytest.raises(RuntimeError, match="not UTF-8"):
        backend.get(tenant_id="tenant-a", resource="orders")
    with pytest.raises(RuntimeError, match="payload is invalid"):
        backend.get(tenant_id="tenant-a", resource="orders")
    with pytest.raises(RuntimeError, match="invalid result"):
        backend.get(tenant_id="tenant-a", resource="orders")
    with pytest.raises(RuntimeError, match="payload is invalid"):
        backend.get(tenant_id="tenant-a", resource="orders")
    with pytest.raises(RuntimeError, match="payload is invalid"):
        backend.get(tenant_id="tenant-a", resource="orders")

    assert read_script.calls == [
        (["businesaios:reliability:lock:tenant-a:orders"], [])
    ] * len(outputs)
