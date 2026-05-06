from __future__ import annotations

from datetime import timedelta

import pytest

from reliability.distributed_lock import InMemoryDistributedLock, utc_now


def test_distributed_lock_enforces_single_owner_until_expiry() -> None:
    lock = InMemoryDistributedLock()
    now = utc_now()

    lease = lock.acquire(tenant_id='tenant-a', resource='execution:run-1', owner_id='worker-a', ttl_seconds=30, now=now)
    blocked = lock.acquire(tenant_id='tenant-a', resource='execution:run-1', owner_id='worker-b', ttl_seconds=30, now=now)
    after_expiry = lock.acquire(
        tenant_id='tenant-a',
        resource='execution:run-1',
        owner_id='worker-b',
        ttl_seconds=30,
        now=now + timedelta(seconds=31),
    )

    assert lease is not None
    assert blocked is None
    assert after_expiry is not None
    assert after_expiry.fencing_token == lease.fencing_token + 1


def test_distributed_lock_renew_rejects_wrong_owner() -> None:
    lock = InMemoryDistributedLock()
    lease = lock.acquire(tenant_id='tenant-a', resource='outbox:msg-1', owner_id='worker-a', ttl_seconds=10)
    assert lease is not None

    with pytest.raises(PermissionError, match='ownership mismatch'):
        lock.renew(
            lease=lease.__class__(
                tenant_id=lease.tenant_id,
                resource=lease.resource,
                owner_id='worker-b',
                fencing_token=lease.fencing_token,
                acquired_at=lease.acquired_at,
                expires_at=lease.expires_at,
            ),
            ttl_seconds=10,
        )


def test_distributed_lock_release_is_idempotent_and_allows_reacquire() -> None:
    lock = InMemoryDistributedLock()
    lease = lock.acquire(tenant_id='tenant-a', resource='execution:run-2', owner_id='worker-a')
    assert lease is not None

    lock.release(lease=lease)
    lock.release(lease=lease)
    reacquired = lock.acquire(tenant_id='tenant-a', resource='execution:run-2', owner_id='worker-b')

    assert reacquired is not None
    assert reacquired.owner_id == 'worker-b'
    assert reacquired.fencing_token == lease.fencing_token + 1
