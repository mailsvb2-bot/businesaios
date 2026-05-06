from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from reliability.distributed_lock import DistributedLock, LockLease


CANON_LEASE_MANAGER = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class LeaseHeartbeat:
    lease: LockLease
    heartbeat_at: datetime = field(default_factory=utc_now)


class LeaseManager:
    def __init__(self, *, lock_provider: DistributedLock, default_ttl_seconds: int = 30) -> None:
        self._lock_provider = lock_provider
        self._default_ttl_seconds = max(1, int(default_ttl_seconds))

    def acquire(
        self,
        *,
        tenant_id: str,
        resource: str,
        owner_id: str,
        ttl_seconds: int | None = None,
        now: datetime | None = None,
    ) -> LockLease | None:
        return self._lock_provider.acquire(
            tenant_id=tenant_id,
            resource=resource,
            owner_id=owner_id,
            ttl_seconds=self._ttl(ttl_seconds),
            now=now,
        )

    def heartbeat(self, *, lease: LockLease, ttl_seconds: int | None = None, now: datetime | None = None) -> LeaseHeartbeat:
        renewed = self._lock_provider.renew(
            lease=lease,
            ttl_seconds=self._ttl(ttl_seconds),
            now=now,
        )
        return LeaseHeartbeat(lease=renewed, heartbeat_at=now or utc_now())

    def release(self, *, lease: LockLease) -> None:
        self._lock_provider.release(lease=lease)

    def _ttl(self, ttl_seconds: int | None) -> int:
        return max(1, int(self._default_ttl_seconds if ttl_seconds is None else ttl_seconds))


__all__ = [
    "CANON_LEASE_MANAGER",
    "LeaseHeartbeat",
    "LeaseManager",
]
