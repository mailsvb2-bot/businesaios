from __future__ import annotations

from tenancy.tenant_audit_scope import TenantAuditScope
from tenancy.tenant_billing_scope import TenantBillingScope
from tenancy.tenant_connector_scope import TenantConnectorScope
from tenancy.tenant_feature_flags import TenantFeatureFlags
from tenancy.tenant_memory_scope import TenantMemoryScope
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, TenantPolicyBundle
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_runtime_limits import TenantRuntimeLimits


def _bundle(tenant_id: str, quotas: dict[str, float]) -> TenantPolicyBundle:
    return TenantPolicyBundle(
        tenant_id=tenant_id,
        feature_flags=TenantFeatureFlags(tenant_id=tenant_id),
        runtime_limits=TenantRuntimeLimits(tenant_id=tenant_id),
        memory_scope=TenantMemoryScope(tenant_id=tenant_id),
        connector_scope=TenantConnectorScope(tenant_id=tenant_id, require_explicit_allowlist=False),
        audit_scope=TenantAuditScope(tenant_id=tenant_id),
        billing_scope=TenantBillingScope(tenant_id=tenant_id),
        quotas=quotas,
    )


def test_tenant_quota_guard_enforces_limits_per_tenant() -> None:
    store = InMemoryTenantPolicyStore()
    store.save(_bundle('tenant-a', {'actions_per_hour': 2}))
    store.save(_bundle('tenant-b', {'actions_per_hour': 2}))
    guard = TenantQuotaGuard(policy_store=store)

    first = guard.consume(tenant_id='tenant-a', dimension='actions_per_hour')
    second = guard.consume(tenant_id='tenant-a', dimension='actions_per_hour')
    blocked = guard.check(tenant_id='tenant-a', dimension='actions_per_hour')
    other_tenant = guard.check(tenant_id='tenant-b', dimension='actions_per_hour')

    assert first.allowed is True
    assert second.used == 2.0
    assert blocked.allowed is False
    assert blocked.remaining == 0.0
    assert other_tenant.allowed is True
    assert guard.snapshot(tenant_id='tenant-b')['actions_per_hour'] == 0.0


def test_tenant_quota_guard_reset_clears_usage() -> None:
    store = InMemoryTenantPolicyStore()
    store.save(_bundle('tenant-a', {'actions_per_day': 1}))
    guard = TenantQuotaGuard(policy_store=store)

    guard.consume(tenant_id='tenant-a', dimension='actions_per_day')
    assert guard.check(tenant_id='tenant-a', dimension='actions_per_day').allowed is False

    guard.reset(tenant_id='tenant-a', dimension='actions_per_day')

    assert guard.check(tenant_id='tenant-a', dimension='actions_per_day').allowed is True


def test_tenant_quota_guard_unconfigured_dimension_is_fail_open_but_tracked_separately() -> None:
    store = InMemoryTenantPolicyStore()
    store.save(_bundle('tenant-a', {'actions_per_hour': 1}))
    guard = TenantQuotaGuard(policy_store=store)

    verdict = guard.consume(tenant_id='tenant-a', dimension='custom_metric')

    assert verdict.allowed is True
    assert verdict.limit is None
    assert guard.snapshot(tenant_id='tenant-a')['custom_metric'] == 1.0
