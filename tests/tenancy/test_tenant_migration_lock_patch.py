from __future__ import annotations

from datetime import timedelta

import pytest

from tenancy.tenant_migration_lock import TenantMigrationLockService
from tenancy.tenant_migration_lock_sqlite import SQLiteTenantMigrationLockBackend
from tenancy.tenant_migration_lock_backend import utc_now


def test_sqlite_tenant_migration_lock_is_exclusive(tmp_path) -> None:
    backend = SQLiteTenantMigrationLockBackend(tmp_path / 'tenant_migration_locks.sqlite3')
    service = TenantMigrationLockService(backend=backend)

    first = service.acquire(
        tenant_id='tenant-zeta',
        operation_id='migrate-schema',
        owner_id='ops-worker-a',
        ttl_seconds=30,
    )
    assert first.allowed is True
    assert first.lock is not None
    assert first.lock.fencing_token == 1

    blocked = service.acquire(
        tenant_id='tenant-zeta',
        operation_id='migrate-billing',
        owner_id='ops-worker-b',
        ttl_seconds=30,
    )
    assert blocked.allowed is False
    assert blocked.reason == 'tenant_migration_locked'
    assert blocked.lock is not None
    assert blocked.lock.operation_id == 'migrate-schema'

    renewed = service.renew(
        tenant_id='tenant-zeta',
        operation_id='migrate-schema',
        owner_id='ops-worker-a',
        ttl_seconds=60,
    )
    assert renewed.owner_id == 'ops-worker-a'
    assert renewed.fencing_token == 1

    released = service.release(
        tenant_id='tenant-zeta',
        operation_id='migrate-schema',
        owner_id='ops-worker-a',
    )
    assert released is True
    assert service.get(tenant_id='tenant-zeta') is None


def test_sqlite_tenant_migration_lock_reaps_expired_record(tmp_path) -> None:
    backend = SQLiteTenantMigrationLockBackend(tmp_path / 'tenant_migration_locks.sqlite3')
    now = utc_now()
    lock = backend.acquire(
        tenant_id='tenant-eta',
        operation_id='rotate-region',
        owner_id='ops-worker-a',
        ttl_seconds=5,
        now=now,
    )
    assert lock is not None
    later = backend.acquire(
        tenant_id='tenant-eta',
        operation_id='rotate-region',
        owner_id='ops-worker-b',
        ttl_seconds=5,
        now=now + timedelta(seconds=10),
    )
    assert later is not None
    assert later.owner_id == 'ops-worker-b'
    assert later.fencing_token == 2


def test_sqlite_tenant_migration_lock_rejects_renew_after_expiry(tmp_path) -> None:
    backend = SQLiteTenantMigrationLockBackend(tmp_path / 'tenant_migration_locks.sqlite3')
    now = utc_now()
    acquired = backend.acquire(
        tenant_id='tenant-iota',
        operation_id='quota-rebuild',
        owner_id='ops-worker-a',
        ttl_seconds=3,
        now=now,
    )
    assert acquired is not None

    with pytest.raises(KeyError):
        backend.renew(
            tenant_id='tenant-iota',
            operation_id='quota-rebuild',
            owner_id='ops-worker-a',
            ttl_seconds=3,
            now=now + timedelta(seconds=10),
        )

    reacquired = backend.acquire(
        tenant_id='tenant-iota',
        operation_id='quota-rebuild',
        owner_id='ops-worker-b',
        ttl_seconds=3,
        now=now + timedelta(seconds=11),
    )
    assert reacquired is not None
    assert reacquired.owner_id == 'ops-worker-b'
    assert reacquired.fencing_token == 2
