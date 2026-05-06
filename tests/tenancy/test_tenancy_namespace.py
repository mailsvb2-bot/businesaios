from __future__ import annotations

import pytest

from tenancy import (
    BillingMode,
    InMemoryTenantPolicyStore,
    InMemoryTenantRegistry,
    QuotaDimension,
    TenantAuditScope,
    TenantBillingScope,
    TenantConnectorScope,
    TenantFeatureFlags,
    TenantMemoryScope,
    TenantPolicyBundle,
    TenantQuotaGuard,
    TenantRecord,
    TenantRuntimeLimits,
)
from tenancy.tenant_context import bind_tenant_id, current_tenant_context, get_current_tenant_id


def _bundle(tenant_id: str = 'tenant-a') -> TenantPolicyBundle:
    return TenantPolicyBundle(
        tenant_id=tenant_id,
        feature_flags=TenantFeatureFlags(tenant_id=tenant_id, flags={'x': True}),
        runtime_limits=TenantRuntimeLimits(tenant_id=tenant_id, max_daily_budget=10.0),
        memory_scope=TenantMemoryScope(tenant_id=tenant_id, namespace_prefixes=('default', 'ops')),
        connector_scope=TenantConnectorScope(
            tenant_id=tenant_id,
            allowed_connectors=('hubspot',),
            secret_scopes_by_connector={'hubspot': ('api_key',)},
        ),
        audit_scope=TenantAuditScope(tenant_id=tenant_id, required_labels={'source': 'test'}),
        billing_scope=TenantBillingScope(
            tenant_id=tenant_id,
            mode=BillingMode.POSTPAID,
            meter_prices={'connector_call': 0.25},
        ),
        quotas={QuotaDimension.ACTIONS_PER_DAY.value: 2.0},
    )


def test_registry_policy_and_quota_are_tenant_strict() -> None:
    registry = InMemoryTenantRegistry()
    record = TenantRecord(tenant_id='tenant-a', display_name='Tenant A', aliases=('tenant-alias',))
    registry.register(record)
    assert registry.require('tenant-a').display_name == 'Tenant A'
    assert registry.resolve('tenant-alias').tenant_id == 'tenant-a'

    store = InMemoryTenantPolicyStore()
    bundle = _bundle('tenant-a')
    store.save(bundle)
    guard = TenantQuotaGuard(policy_store=store)

    verdict1 = guard.consume(tenant_id='tenant-a', dimension=QuotaDimension.ACTIONS_PER_DAY.value)
    verdict2 = guard.consume(tenant_id='tenant-a', dimension=QuotaDimension.ACTIONS_PER_DAY.value)
    verdict3 = guard.consume(tenant_id='tenant-a', dimension=QuotaDimension.ACTIONS_PER_DAY.value)

    assert verdict1.allowed is True
    assert verdict2.allowed is True
    assert verdict3.allowed is False
    assert verdict3.reason == 'quota exceeded'


def test_memory_connector_audit_and_billing_scopes_enforce_boundaries() -> None:
    bundle = _bundle('tenant-b')
    assert bundle.memory_scope.qualify_namespace(business_id='biz-1', namespace='default/events').startswith('tenant/tenant-b/')
    assert bundle.connector_scope.allowed_secret_scopes('hubspot') == ('api_key',)
    scrubbed = bundle.audit_scope.scrub({'password': 'secret', 'payload': {'x': 1}})
    assert scrubbed['password'] == '[REDACTED]'
    assert scrubbed['payload'] == '[OMITTED]'
    assert scrubbed['source'] == 'test'
    assert bundle.billing_scope.estimate_charge(meter_name='connector_call', quantity=4) == 1.0


def test_context_binding_is_scoped_and_resets() -> None:
    assert current_tenant_context() is None
    with bind_tenant_id('tenant-c', route='api'):
        assert get_current_tenant_id(require=True) == 'tenant-c'
        assert current_tenant_context().metadata['route'] == 'api'
    assert current_tenant_context() is None


def test_cross_tenant_policy_bundle_is_rejected() -> None:
    with pytest.raises(ValueError):
        TenantPolicyBundle(
            tenant_id='tenant-a',
            feature_flags=TenantFeatureFlags(tenant_id='tenant-b'),
            runtime_limits=TenantRuntimeLimits(tenant_id='tenant-a'),
            memory_scope=TenantMemoryScope(tenant_id='tenant-a'),
            connector_scope=TenantConnectorScope(tenant_id='tenant-a'),
            audit_scope=TenantAuditScope(tenant_id='tenant-a'),
            billing_scope=TenantBillingScope(tenant_id='tenant-a'),
        ).validate()
