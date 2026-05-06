from __future__ import annotations

from tenancy.tenant_admission_coordinator import LeaseStoreAdmissionBackend
from tenancy.tenant_admission_contract import TenantAdmissionLease
from tenancy.tenant_runtime_invariant_checks import TenantRuntimeInvariantChecks
from tenancy.tenant_runtime_lease_store import InMemoryTenantRuntimeLeaseStore


def test_runtime_and_admission_semantic_parity() -> None:
    store = InMemoryTenantRuntimeLeaseStore()
    backend = LeaseStoreAdmissionBackend(lease_store=store)
    result = store.acquire(
        tenant_id='tenant-a',
        run_id='run-1',
        owner_id='worker-1',
        limit=3,
        ttl_seconds=30,
        labels={'kind': 'sync'},
    )
    assert result.allowed is True and result.lease is not None
    report = TenantRuntimeInvariantChecks().evaluate_semantic_parity(
        tenant_id='tenant-a',
        leases=store.list_active(tenant_id='tenant-a'),
        admissions=backend.list_active(tenant_id='tenant-a'),
    )
    assert report.ok is True
    assert report.violations == ()


def test_parity_detects_owner_mismatch() -> None:
    store = InMemoryTenantRuntimeLeaseStore()
    lease = store.acquire(
        tenant_id='tenant-a',
        run_id='run-1',
        owner_id='worker-1',
        limit=3,
        ttl_seconds=30,
    ).lease
    assert lease is not None
    mismatched = TenantAdmissionLease(
        tenant_id=lease.tenant_id,
        run_id=lease.run_id,
        owner_id='worker-2',
        fencing_token=lease.fencing_token,
        acquired_at=lease.acquired_at,
        expires_at=lease.expires_at,
    )
    report = TenantRuntimeInvariantChecks().evaluate_semantic_parity(
        tenant_id='tenant-a',
        leases=(lease,),
        admissions=(mismatched,),
    )
    assert report.ok is False
    assert {item.code for item in report.violations} == {'owner_mismatch'}
