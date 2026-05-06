from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
import os
import threading

from core.tenancy.normalization import require_tenant_id


CANON_DISTRIBUTED_LOCK = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_ttl(ttl_seconds: int) -> int:
    ttl = int(ttl_seconds)
    if ttl <= 0:
        raise ValueError("ttl_seconds must be > 0")
    return ttl


def _normalize_resource(resource: str) -> str:
    value = str(resource or "").strip()
    if not value:
        raise ValueError("resource is required")
    return value


def _normalize_owner_id(owner_id: str) -> str:
    value = str(owner_id or "").strip()
    if not value:
        raise ValueError("owner_id is required")
    return value


@dataclass(frozen=True)
class LockLease:
    tenant_id: str
    resource: str
    owner_id: str
    fencing_token: int
    acquired_at: datetime = field(default_factory=utc_now)
    expires_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        _normalize_resource(self.resource)
        _normalize_owner_id(self.owner_id)
        if int(self.fencing_token) <= 0:
            raise ValueError("fencing_token must be > 0")
        if self.acquired_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        if self.expires_at <= self.acquired_at:
            raise ValueError("expires_at must be > acquired_at")

    def is_live(self, *, now: datetime | None = None) -> bool:
        moment = now or utc_now()
        if moment.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return moment < self.expires_at


class DistributedLock(Protocol):
    def acquire(
        self,
        *,
        tenant_id: str,
        resource: str,
        owner_id: str,
        ttl_seconds: int = 30,
        now: datetime | None = None,
    ) -> LockLease | None: ...

    def renew(
        self,
        *,
        lease: LockLease,
        ttl_seconds: int = 30,
        now: datetime | None = None,
    ) -> LockLease: ...

    def release(self, *, lease: LockLease) -> None: ...

    def get(self, *, tenant_id: str, resource: str) -> LockLease | None: ...


class InMemoryDistributedLock(DistributedLock):
    def __init__(self) -> None:
        self._locks: dict[tuple[str, str], LockLease] = {}
        self._tokens: dict[tuple[str, str], int] = {}
        self._lock = threading.RLock()

    def acquire(
        self,
        *,
        tenant_id: str,
        resource: str,
        owner_id: str,
        ttl_seconds: int = 30,
        now: datetime | None = None,
    ) -> LockLease | None:
        tid = require_tenant_id(tenant_id)
        res = _normalize_resource(resource)
        owner = _normalize_owner_id(owner_id)
        ttl = _normalize_ttl(ttl_seconds)
        moment = now or utc_now()
        cache_key = (tid, res)
        with self._lock:
            current = self._locks.get(cache_key)
            if current is not None and current.is_live(now=moment):
                return None

            token = int(self._tokens.get(cache_key, 0)) + 1
            self._tokens[cache_key] = token
            lease = LockLease(
                tenant_id=tid,
                resource=res,
                owner_id=owner,
                fencing_token=token,
                acquired_at=moment,
                expires_at=moment + timedelta(seconds=ttl),
            )
            lease.validate()
            self._locks[cache_key] = lease
            return lease

    def renew(
        self,
        *,
        lease: LockLease,
        ttl_seconds: int = 30,
        now: datetime | None = None,
    ) -> LockLease:
        lease.validate()
        ttl = _normalize_ttl(ttl_seconds)
        moment = now or utc_now()
        cache_key = (lease.tenant_id, lease.resource)
        with self._lock:
            current = self._locks.get(cache_key)
            if current is None:
                raise PermissionError("lease no longer exists")
            if not current.is_live(now=moment):
                self._locks.pop(cache_key, None)
                raise PermissionError("lease has expired")
            if current.fencing_token != lease.fencing_token or current.owner_id != lease.owner_id:
                raise PermissionError("lease ownership mismatch")

            renewed = LockLease(
                tenant_id=lease.tenant_id,
                resource=lease.resource,
                owner_id=lease.owner_id,
                fencing_token=lease.fencing_token,
                acquired_at=lease.acquired_at,
                expires_at=moment + timedelta(seconds=ttl),
            )
            renewed.validate()
            self._locks[cache_key] = renewed
            return renewed

    def release(self, *, lease: LockLease) -> None:
        lease.validate()
        cache_key = (lease.tenant_id, lease.resource)
        with self._lock:
            current = self._locks.get(cache_key)
            if current is not None and current.fencing_token == lease.fencing_token and current.owner_id == lease.owner_id:
                self._locks.pop(cache_key, None)

    def get(self, *, tenant_id: str, resource: str) -> LockLease | None:
        cache_key = (require_tenant_id(tenant_id), _normalize_resource(resource))
        with self._lock:
            lease = self._locks.get(cache_key)
            if lease is None:
                return None
            if not lease.is_live():
                self._locks.pop(cache_key, None)
                return None
            return lease


class PluggableDistributedLock(DistributedLock):
    """Thin adapter around a backend implementation.

    Exists to keep the canonical lock contract stable while allowing the
    runtime to swap persistence backends without introducing a second path.
    """

    def __init__(self, *, backend: DistributedLock) -> None:
        self._backend = backend

    @property
    def backend(self) -> DistributedLock:
        return self._backend

    def acquire(self, **kwargs: Any) -> LockLease | None:
        return self._backend.acquire(**kwargs)

    def renew(self, **kwargs: Any) -> LockLease:
        return self._backend.renew(**kwargs)

    def release(self, **kwargs: Any) -> None:
        self._backend.release(**kwargs)

    def get(self, **kwargs: Any) -> LockLease | None:
        return self._backend.get(**kwargs)


def build_distributed_lock(
    *,
    backend: DistributedLock | None = None,
    backend_name: str | None = None,
    redis_url: str | None = None,
    postgres_dsn: str | None = None,
    postgres_table_prefix: str = "reliability",
    application_name: str = "businesaios-reliability-lock",
    statement_timeout_ms: int = 30000,
    lock_timeout_ms: int = 5000,
) -> DistributedLock:
    if backend is not None:
        return PluggableDistributedLock(backend=backend)

    selected = str(backend_name or os.getenv("RELIABILITY_LOCK_BACKEND", "memory")).strip().lower()
    if selected in {"", "memory", "inmemory", "in-memory"}:
        return InMemoryDistributedLock()
    if selected == "redis":
        from reliability.distributed_lock_redis import RedisDistributedLockBackend

        return PluggableDistributedLock(
            backend=RedisDistributedLockBackend(
                redis_url=redis_url or os.getenv("RELIABILITY_REDIS_URL"),
            )
        )
    if selected in {"postgres", "postgresql"}:
        from reliability.distributed_lock_postgres import PostgresDistributedLockBackend

        dsn = str(postgres_dsn or os.getenv("RELIABILITY_POSTGRES_DSN") or "").strip()
        if not dsn:
            raise ValueError("postgres_dsn is required for postgres distributed lock backend")
        return PluggableDistributedLock(
            backend=PostgresDistributedLockBackend(
                dsn=dsn,
                application_name=application_name,
                statement_timeout_ms=statement_timeout_ms,
                lock_timeout_ms=lock_timeout_ms,
                table_prefix=postgres_table_prefix,
            )
        )
    raise ValueError(f"unsupported distributed lock backend: {selected}")


__all__ = [
    "CANON_DISTRIBUTED_LOCK",
    "DistributedLock",
    "InMemoryDistributedLock",
    "LockLease",
    "PluggableDistributedLock",
    "build_distributed_lock",
    "utc_now",
]
