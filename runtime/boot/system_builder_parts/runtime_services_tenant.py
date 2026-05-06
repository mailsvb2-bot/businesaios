from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

from tenancy.tenant_admission_coordinator import LeaseStoreAdmissionBackend, TenantAdmissionCoordinator
from tenancy.tenant_contract import TenantPlan, TenantRecord
from tenancy.tenant_execution_budget_guard import TenantExecutionBudgetGuard
from tenancy.tenant_metrics_sqlite import SQLiteTenantMetricsStore
from tenancy.tenant_migration_lock import TenantMigrationLockService
from tenancy.tenant_migration_lock_sqlite import SQLiteTenantMigrationLockBackend
from tenancy.tenant_policy_store import build_default_tenant_policy_bundle, build_default_tenant_policy_store
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_registry import build_default_tenant_registry
from tenancy.tenant_runtime_fencing_registry import InMemoryTenantRuntimeFencingRegistry
from tenancy.tenant_runtime_isolation import TenantRuntimeIsolation
from tenancy.tenant_runtime_lease_sqlite import SQLiteTenantRuntimeLeaseStore
from tenancy.tenant_runtime_reconciliation import TenantRuntimeReconciler
from tenancy.tenant_schema_version_guard import TenantSchemaVersionExpectation
from tenancy.tenant_startup_selfcheck import TenantStartupSelfcheck


def build_tenant_runtime_services(*, tenant_id: str):
    tenant_registry = build_default_tenant_registry()
    tenant_policy_store = build_default_tenant_policy_store()
    if tenant_registry.lookup(tenant_id) is None:
        tenant_registry.register(TenantRecord(tenant_id=tenant_id, display_name=tenant_id, plan=TenantPlan.STARTER))
    if tenant_policy_store.get(tenant_id) is None:
        tenant_policy_store.save(build_default_tenant_policy_bundle(tenant_id))
    tenant_quota_guard = TenantQuotaGuard(policy_store=tenant_policy_store)
    tenant_runtime_isolation = TenantRuntimeIsolation(policy_store=tenant_policy_store)
    tenant_execution_budget_guard = TenantExecutionBudgetGuard(policy_store=tenant_policy_store, quota_guard=tenant_quota_guard)
    tenant_runtime_lease_store = SQLiteTenantRuntimeLeaseStore()
    tenant_admission_backend = LeaseStoreAdmissionBackend(lease_store=tenant_runtime_lease_store)
    tenant_admission_coordinator = TenantAdmissionCoordinator(policy_store=tenant_policy_store, backend=tenant_admission_backend)
    tenant_runtime_fencing_registry = InMemoryTenantRuntimeFencingRegistry()
    tenant_metrics_store = SQLiteTenantMetricsStore()
    tenant_migration_lock_backend = SQLiteTenantMigrationLockBackend()
    tenant_migration_lock_service = TenantMigrationLockService(backend=tenant_migration_lock_backend, tenant_registry=tenant_registry)
    tenant_runtime_reconciler = TenantRuntimeReconciler(lease_store=tenant_runtime_lease_store, admission_backend=tenant_admission_backend)
    tenant_startup_selfcheck = TenantStartupSelfcheck(lease_store=tenant_runtime_lease_store, admission_backend=tenant_admission_backend)
    tenant_startup_selfcheck.run(
        tenant_id=tenant_id,
        schema_backends=(
            (tenant_runtime_lease_store, TenantSchemaVersionExpectation(component='tenant_runtime_leases', minimum_version=1, maximum_version=1)),
            (tenant_metrics_store, TenantSchemaVersionExpectation(component='tenant_metrics', minimum_version=1, maximum_version=1)),
            (tenant_migration_lock_backend, TenantSchemaVersionExpectation(component='tenant_migration_locks', minimum_version=1, maximum_version=1)),
        ),
        clock_readers=(tenant_runtime_lease_store, tenant_metrics_store, tenant_migration_lock_backend),
        limit=tenant_policy_store.require(tenant_id).runtime_limits.max_concurrent_runs,
    )
    return {
        'tenant_registry': tenant_registry,
        'tenant_policy_store': tenant_policy_store,
        'tenant_quota_guard': tenant_quota_guard,
        'tenant_runtime_isolation': tenant_runtime_isolation,
        'tenant_execution_budget_guard': tenant_execution_budget_guard,
        'tenant_runtime_lease_store': tenant_runtime_lease_store,
        'tenant_admission_backend': tenant_admission_backend,
        'tenant_admission_coordinator': tenant_admission_coordinator,
        'tenant_runtime_reconciler': tenant_runtime_reconciler,
        'tenant_runtime_fencing_registry': tenant_runtime_fencing_registry,
        'tenant_metrics_store': tenant_metrics_store,
        'tenant_migration_lock_backend': tenant_migration_lock_backend,
        'tenant_migration_lock_service': tenant_migration_lock_service,
        'tenant_startup_selfcheck': tenant_startup_selfcheck,
    }
