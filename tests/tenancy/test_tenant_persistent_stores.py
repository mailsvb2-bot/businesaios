from __future__ import annotations

from tenancy.tenant_contract import TenantPlan, TenantRecord, TenantStatus
from tenancy.tenant_registry import PersistentTenantRegistry
from tenancy.tenant_policy_store import PersistentTenantPolicyStore, TenantPolicyBundle
from tenancy.tenant_feature_flags import TenantFeatureFlags
from tenancy.tenant_runtime_limits import TenantRuntimeLimits
from tenancy.tenant_memory_scope import TenantMemoryScope
from tenancy.tenant_connector_scope import TenantConnectorScope
from tenancy.tenant_audit_scope import TenantAuditScope
from tenancy.tenant_billing_scope import TenantBillingScope


def test_persistent_tenant_registry_roundtrip(tmp_path) -> None:
    path = tmp_path / 'registry.json'
    registry = PersistentTenantRegistry(path=path)
    registry.register(TenantRecord(tenant_id='tenant-a', display_name='Tenant A', plan=TenantPlan.GROWTH, status=TenantStatus.ACTIVE))
    reloaded = PersistentTenantRegistry(path=path)
    record = reloaded.require('tenant-a')
    assert record.display_name == 'Tenant A'
    assert record.plan is TenantPlan.GROWTH


def test_persistent_tenant_policy_store_roundtrip(tmp_path) -> None:
    path = tmp_path / 'policies.json'
    store = PersistentTenantPolicyStore(path=path)
    bundle = TenantPolicyBundle(
        tenant_id='tenant-a',
        feature_flags=TenantFeatureFlags(tenant_id='tenant-a', flags={'admin_console': True}),
        runtime_limits=TenantRuntimeLimits(tenant_id='tenant-a'),
        memory_scope=TenantMemoryScope(tenant_id='tenant-a'),
        connector_scope=TenantConnectorScope(tenant_id='tenant-a'),
        audit_scope=TenantAuditScope(tenant_id='tenant-a'),
        billing_scope=TenantBillingScope(tenant_id='tenant-a'),
        quotas={'api.requests_per_minute': 100.0},
    )
    store.save(bundle)
    reloaded = PersistentTenantPolicyStore(path=path)
    loaded = reloaded.require('tenant-a')
    assert loaded.feature_flags.flags['admin_console'] is True
    assert loaded.quotas['api.requests_per_minute'] == 100.0
