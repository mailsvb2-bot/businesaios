from __future__ import annotations

from datetime import datetime, timezone, UTC
from typing import Callable

import pytest

from reliability.distributed_lock import InMemoryDistributedLock

UTC = UTC


def _t(second: int = 0) -> datetime:
    return datetime(2026, 1, 1, 0, 0, second, tzinfo=UTC)


BackendFactory = Callable[[], object]


@pytest.fixture(params=[lambda: InMemoryDistributedLock()], ids=['memory'])
def backend_factory(request) -> BackendFactory:
    return request.param


def test_backend_parity_acquire_renew_release(backend_factory: BackendFactory) -> None:
    backend = backend_factory()
    lease = backend.acquire(tenant_id='tenant-a', resource='scheduler', owner_id='node-1', ttl_seconds=10, now=_t())
    assert lease is not None
    assert lease.fencing_token == 1
    renewed = backend.renew(lease=lease, ttl_seconds=10, now=_t(5))
    assert renewed.fencing_token == 1
    assert renewed.owner_id == 'node-1'
    backend.release(lease=renewed)
    assert backend.get(tenant_id='tenant-a', resource='scheduler') is None


def test_backend_parity_reacquire_after_expiry(backend_factory: BackendFactory) -> None:
    backend = backend_factory()
    lease1 = backend.acquire(tenant_id='tenant-a', resource='scheduler', owner_id='node-1', ttl_seconds=5, now=_t())
    assert lease1 is not None
    lease2 = backend.acquire(tenant_id='tenant-a', resource='scheduler', owner_id='node-2', ttl_seconds=5, now=_t(6))
    assert lease2 is not None
    assert lease2.fencing_token == lease1.fencing_token + 1
