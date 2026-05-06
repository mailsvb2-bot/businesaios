from __future__ import annotations

from datetime import timedelta

import pytest

from tenancy.tenant_runtime_lease_store import InMemoryTenantRuntimeLeaseStore, utc_now


def test_inmemory_runtime_lease_store_enforces_capacity_and_reaps_expired() -> None:
    store = InMemoryTenantRuntimeLeaseStore()
    now = utc_now()

    first = store.acquire(
        tenant_id='tenant-alpha',
        run_id='run-1',
        owner_id='worker-a',
        limit=1,
        ttl_seconds=5,
        labels={'phase': 'execute'},
        now=now,
    )
    assert first.allowed is True
    assert first.lease is not None
    assert first.lease.fencing_token == 1

    denied = store.acquire(
        tenant_id='tenant-alpha',
        run_id='run-2',
        owner_id='worker-b',
        limit=1,
        ttl_seconds=5,
        labels={'phase': 'execute'},
        now=now,
    )
    assert denied.allowed is False
    assert denied.reason == 'tenant_runtime_capacity_exceeded'

    same = store.acquire(
        tenant_id='tenant-alpha',
        run_id='run-1',
        owner_id='worker-a',
        limit=1,
        ttl_seconds=10,
        labels={'phase': 'execute'},
        now=now + timedelta(seconds=1),
    )
    assert same.allowed is True
    assert same.reason == 'already_acquired'
    assert same.lease is not None
    assert same.lease.fencing_token == 1

    expired = store.reap_expired(now=now + timedelta(seconds=20))
    assert len(expired) == 1
    assert expired[0].tenant_id == 'tenant-alpha'
    assert store.get(tenant_id='tenant-alpha', run_id='run-1') is None

    second = store.acquire(
        tenant_id='tenant-alpha',
        run_id='run-3',
        owner_id='worker-c',
        limit=1,
        ttl_seconds=5,
        labels={'phase': 'execute'},
        now=now + timedelta(seconds=21),
    )
    assert second.allowed is True
    assert second.lease is not None
    assert second.lease.fencing_token == 2


def test_inmemory_runtime_lease_store_rejects_owner_or_label_drift() -> None:
    store = InMemoryTenantRuntimeLeaseStore()
    now = utc_now()
    acquired = store.acquire(
        tenant_id='tenant-beta',
        run_id='run-9',
        owner_id='worker-a',
        limit=2,
        ttl_seconds=30,
        labels={'channel': 'email'},
        now=now,
    )
    assert acquired.allowed is True

    wrong_owner = store.acquire(
        tenant_id='tenant-beta',
        run_id='run-9',
        owner_id='worker-b',
        limit=2,
        ttl_seconds=30,
        labels={'channel': 'email'},
        now=now,
    )
    assert wrong_owner.allowed is False
    assert wrong_owner.reason == 'lease_owned_by_another_owner'

    wrong_labels = store.acquire(
        tenant_id='tenant-beta',
        run_id='run-9',
        owner_id='worker-a',
        limit=2,
        ttl_seconds=30,
        labels={'channel': 'sms'},
        now=now,
    )
    assert wrong_labels.allowed is False
    assert wrong_labels.reason == 'lease_labels_mismatch'


def test_inmemory_runtime_lease_store_rejects_renew_after_expiry() -> None:
    store = InMemoryTenantRuntimeLeaseStore()
    now = utc_now()
    acquired = store.acquire(
        tenant_id='tenant-kappa',
        run_id='run-expire',
        owner_id='worker-a',
        limit=1,
        ttl_seconds=3,
        labels={'phase': 'execute'},
        now=now,
    )
    assert acquired.allowed is True

    with pytest.raises(KeyError):
        store.renew(
            tenant_id='tenant-kappa',
            run_id='run-expire',
            owner_id='worker-a',
            ttl_seconds=5,
            now=now + timedelta(seconds=10),
        )


def test_inmemory_runtime_lease_store_get_drops_expired_record() -> None:
    store = InMemoryTenantRuntimeLeaseStore()
    now = utc_now()
    acquired = store.acquire(tenant_id='tenant-expire', run_id='run-expire', owner_id='worker-a', limit=1, ttl_seconds=1, now=now)
    assert acquired.allowed is True
    assert store.get(tenant_id='tenant-expire', run_id='run-expire') is not None
    expired = store.reap_expired(now=now + timedelta(seconds=2))
    assert len(expired) == 1
    assert store.get(tenant_id='tenant-expire', run_id='run-expire') is None
