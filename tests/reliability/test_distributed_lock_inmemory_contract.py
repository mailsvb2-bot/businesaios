from __future__ import annotations

from datetime import timedelta

import pytest

from reliability.distributed_lock import InMemoryDistributedLock, utc_now
from reliability.lease_fencing_token import LeaseFencingToken


@pytest.fixture()
def backend() -> InMemoryDistributedLock:
    return InMemoryDistributedLock()


def test_acquire_returns_first_live_lease(backend: InMemoryDistributedLock) -> None:
    now = utc_now()
    lease = backend.acquire(tenant_id='tenant-a', resource='scheduler', owner_id='node-1', ttl_seconds=30, now=now)
    assert lease is not None
    assert lease.tenant_id == 'tenant-a'
    assert lease.resource == 'scheduler'
    assert lease.owner_id == 'node-1'
    assert lease.fencing_token == 1
    assert lease.is_live(now=now + timedelta(seconds=10)) is True


def test_second_acquire_is_blocked_while_first_lease_is_live(backend: InMemoryDistributedLock) -> None:
    now = utc_now()
    lease1 = backend.acquire(tenant_id='tenant-a', resource='scheduler', owner_id='node-1', ttl_seconds=30, now=now)
    assert lease1 is not None
    lease2 = backend.acquire(tenant_id='tenant-a', resource='scheduler', owner_id='node-2', ttl_seconds=30, now=now + timedelta(seconds=5))
    assert lease2 is None


def test_acquire_at_exact_expiry_boundary_is_allowed(backend: InMemoryDistributedLock) -> None:
    now = utc_now()
    lease1 = backend.acquire(tenant_id='tenant-a', resource='scheduler', owner_id='node-1', ttl_seconds=5, now=now)
    assert lease1 is not None
    lease2 = backend.acquire(tenant_id='tenant-a', resource='scheduler', owner_id='node-2', ttl_seconds=5, now=now + timedelta(seconds=5))
    assert lease2 is not None
    assert lease2.owner_id == 'node-2'
    assert lease2.fencing_token == 2


def test_reacquire_after_expiry_gets_new_fencing_token(backend: InMemoryDistributedLock) -> None:
    now = utc_now()
    lease1 = backend.acquire(tenant_id='tenant-a', resource='scheduler', owner_id='node-1', ttl_seconds=5, now=now)
    assert lease1 is not None
    lease2 = backend.acquire(tenant_id='tenant-a', resource='scheduler', owner_id='node-2', ttl_seconds=5, now=now + timedelta(seconds=6))
    assert lease2 is not None
    assert lease2.fencing_token == 2
    assert LeaseFencingToken(lease2.fencing_token) > LeaseFencingToken(lease1.fencing_token)


def test_renew_preserves_fencing_token_and_extends_expiry(backend: InMemoryDistributedLock) -> None:
    now = utc_now()
    lease = backend.acquire(tenant_id='tenant-a', resource='recovery', owner_id='node-1', ttl_seconds=10, now=now)
    assert lease is not None
    renewal_moment = now + timedelta(seconds=5)
    renewed = backend.renew(lease=lease, ttl_seconds=20, now=renewal_moment)
    assert renewed.fencing_token == lease.fencing_token
    assert renewed.acquired_at == lease.acquired_at
    assert renewed.expires_at == renewal_moment + timedelta(seconds=20)


def test_renew_rejects_after_expiry(backend: InMemoryDistributedLock) -> None:
    now = utc_now()
    lease = backend.acquire(tenant_id='tenant-a', resource='recovery', owner_id='node-1', ttl_seconds=5, now=now)
    assert lease is not None
    with pytest.raises(PermissionError):
        backend.renew(lease=lease, ttl_seconds=5, now=now + timedelta(seconds=6))


def test_renew_rejects_stale_split_brain_writer(backend: InMemoryDistributedLock) -> None:
    now = utc_now()
    stale = backend.acquire(tenant_id='tenant-a', resource='scheduler', owner_id='node-1', ttl_seconds=5, now=now)
    assert stale is not None
    current = backend.acquire(tenant_id='tenant-a', resource='scheduler', owner_id='node-2', ttl_seconds=5, now=now + timedelta(seconds=6))
    assert current is not None
    assert current.fencing_token == 2
    with pytest.raises(PermissionError):
        backend.renew(lease=stale, ttl_seconds=5, now=now + timedelta(seconds=6))


def test_release_by_stale_owner_does_not_delete_newer_lease(backend: InMemoryDistributedLock) -> None:
    now = utc_now()
    stale = backend.acquire(tenant_id='tenant-a', resource='scheduler', owner_id='node-1', ttl_seconds=5, now=now)
    assert stale is not None
    current = backend.acquire(tenant_id='tenant-a', resource='scheduler', owner_id='node-2', ttl_seconds=5, now=now + timedelta(seconds=6))
    assert current is not None
    backend.release(lease=stale)
    observed = backend.get(tenant_id='tenant-a', resource='scheduler')
    assert observed is not None
    assert observed.owner_id == 'node-2'
    assert observed.fencing_token == 2


def test_get_cleans_expired_lease_and_returns_none(backend: InMemoryDistributedLock) -> None:
    now = utc_now()
    lease = backend.acquire(tenant_id='tenant-a', resource='scheduler', owner_id='node-1', ttl_seconds=5, now=now)
    assert lease is not None
    expired = lease.__class__(tenant_id=lease.tenant_id, resource=lease.resource, owner_id=lease.owner_id, fencing_token=lease.fencing_token, acquired_at=lease.acquired_at, expires_at=now - timedelta(seconds=1))
    backend._locks[(lease.tenant_id, lease.resource)] = expired
    observed = backend.get(tenant_id='tenant-a', resource='scheduler')
    assert observed is None
