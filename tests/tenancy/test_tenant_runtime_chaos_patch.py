from __future__ import annotations

from tenancy.tenant_admission_coordinator import LeaseStoreAdmissionBackend
from tenancy.tenant_runtime_invariant_checks import TenantRuntimeInvariantChecks
from tenancy.tenant_runtime_reconciliation import TenantRuntimeReconciler
from tenancy.tenant_runtime_lease_store import InMemoryTenantRuntimeLeaseStore, utc_now


class DummyAdmissionBackend(LeaseStoreAdmissionBackend):
    pass


def test_reconciliation_releases_orphan_runtime_lease() -> None:
    store = InMemoryTenantRuntimeLeaseStore()
    now = utc_now()
    result = store.acquire(
        tenant_id='tenant-a',
        run_id='run-1',
        owner_id='worker-1',
        limit=5,
        ttl_seconds=60,
        labels={'source': 'test'},
        now=now,
    )
    assert result.allowed is True
    backend = DummyAdmissionBackend(lease_store=InMemoryTenantRuntimeLeaseStore())
    reconciler = TenantRuntimeReconciler(lease_store=store, admission_backend=backend)
    outcome = reconciler.reconcile(tenant_id='tenant-a', limit=5, now=now)
    assert outcome.released_runtime_runs == ('run-1',)
    assert store.get(tenant_id='tenant-a', run_id='run-1') is None


def test_runtime_invariant_checks_detect_duplicate_tokens() -> None:
    store = InMemoryTenantRuntimeLeaseStore()
    now = utc_now()
    a = store.acquire(tenant_id='tenant-a', run_id='run-1', owner_id='w1', limit=5, ttl_seconds=60, now=now)
    b = store.acquire(tenant_id='tenant-a', run_id='run-2', owner_id='w2', limit=5, ttl_seconds=60, now=now)
    assert a.lease is not None and b.lease is not None
    duplicate = b.lease.__class__(
        tenant_id=b.lease.tenant_id,
        run_id=b.lease.run_id,
        owner_id=b.lease.owner_id,
        slot_id=b.lease.slot_id,
        fencing_token=a.lease.fencing_token,
        acquired_at=b.lease.acquired_at,
        heartbeat_at=b.lease.heartbeat_at,
        expires_at=b.lease.expires_at,
        labels=b.lease.labels,
    )
    checks = TenantRuntimeInvariantChecks()
    report = checks.evaluate_runtime_leases(tenant_id='tenant-a', leases=(a.lease, duplicate), limit=5, now=now)
    assert report.ok is False
    assert {item.code for item in report.violations} == {'duplicate_fencing_token'}
