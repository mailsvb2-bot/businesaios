from __future__ import annotations

from tenancy.tenant_admission_coordinator import LeaseStoreAdmissionBackend, TenantAdmissionCoordinator
from tenancy.tenant_audit_scope import TenantAuditScope
from tenancy.tenant_billing_scope import TenantBillingScope
from tenancy.tenant_connector_scope import TenantConnectorScope
from tenancy.tenant_feature_flags import TenantFeatureFlags
from tenancy.tenant_memory_scope import TenantMemoryScope
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, TenantPolicyBundle
from tenancy.tenant_runtime_lease_store import InMemoryTenantRuntimeLeaseStore
from tenancy.tenant_runtime_limits import TenantRuntimeLimits


def _bundle(tenant_id: str, *, max_concurrent_runs: int = 1) -> TenantPolicyBundle:
    return TenantPolicyBundle(
        tenant_id=tenant_id,
        feature_flags=TenantFeatureFlags(tenant_id=tenant_id),
        runtime_limits=TenantRuntimeLimits(tenant_id=tenant_id, max_concurrent_runs=max_concurrent_runs),
        memory_scope=TenantMemoryScope(tenant_id=tenant_id),
        connector_scope=TenantConnectorScope(tenant_id=tenant_id),
        audit_scope=TenantAuditScope(tenant_id=tenant_id),
        billing_scope=TenantBillingScope(tenant_id=tenant_id),
        quotas={},
    )


def test_tenant_admission_coordinator_respects_policy_limit() -> None:
    policy_store = InMemoryTenantPolicyStore()
    policy_store.save(_bundle('tenant-gamma', max_concurrent_runs=1))
    backend = LeaseStoreAdmissionBackend(lease_store=InMemoryTenantRuntimeLeaseStore())
    coordinator = TenantAdmissionCoordinator(policy_store=policy_store, backend=backend)

    first = coordinator.admit(
        tenant_id='tenant-gamma',
        run_id='run-1',
        owner_id='worker-1',
        ttl_seconds=20,
        labels={'flow': 'goal-execution'},
    )
    assert first.allowed is True
    assert first.lease is not None
    assert first.active_runs == 1

    second = coordinator.admit(
        tenant_id='tenant-gamma',
        run_id='run-2',
        owner_id='worker-2',
        ttl_seconds=20,
        labels={'flow': 'goal-execution'},
    )
    assert second.allowed is False
    assert second.reason == 'tenant_runtime_capacity_exceeded'

    released = coordinator.release(
        tenant_id='tenant-gamma',
        run_id='run-1',
        owner_id='worker-1',
    )
    assert released is True

    third = coordinator.admit(
        tenant_id='tenant-gamma',
        run_id='run-3',
        owner_id='worker-3',
        ttl_seconds=20,
        labels={'flow': 'goal-execution'},
    )
    assert third.allowed is True
    assert third.lease is not None
    assert third.lease.fencing_token == 2
