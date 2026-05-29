from __future__ import annotations

import pytest

from tenancy.tenant_context import bind_tenant_id, current_tenant_context, get_current_tenant_id
from tenancy.tenant_contract import TenantPlan, TenantRecord
from tenancy.tenant_registry import InMemoryTenantRegistry


def test_tenant_context_binding_is_scoped_and_restored() -> None:
    assert current_tenant_context() is None

    with bind_tenant_id('tenant-a', source='outer'):
        assert get_current_tenant_id(require=True) == 'tenant-a'
        outer = current_tenant_context()
        assert outer is not None
        assert outer.metadata['source'] == 'outer'

        with bind_tenant_id('tenant-b', source='inner'):
            assert get_current_tenant_id(require=True) == 'tenant-b'
            inner = current_tenant_context()
            assert inner is not None
            assert inner.metadata['source'] == 'inner'

        assert get_current_tenant_id(require=True) == 'tenant-a'

    assert current_tenant_context() is None


def test_tenant_registry_resolves_alias_without_cross_tenant_collision() -> None:
    registry = InMemoryTenantRegistry()
    registry.register(TenantRecord(tenant_id='tenant-a', display_name='Tenant A', aliases=('acme',), plan=TenantPlan.ENTERPRISE))
    registry.register(TenantRecord(tenant_id='tenant-b', display_name='Tenant B', aliases=('globex',), plan=TenantPlan.STARTER))

    assert registry.resolve('acme').tenant_id == 'tenant-a'
    assert registry.resolve('globex').tenant_id == 'tenant-b'
    assert registry.resolve('tenant-a').tenant_id == 'tenant-a'
    assert registry.resolve('unknown') is None


def test_tenant_registry_rejects_alias_collision_between_tenants() -> None:
    registry = InMemoryTenantRegistry()
    registry.register(TenantRecord(tenant_id='tenant-a', display_name='Tenant A', aliases=('shared',), plan=TenantPlan.ENTERPRISE))

    with pytest.raises(ValueError, match='alias collision'):
        registry.register(TenantRecord(tenant_id='tenant-b', display_name='Tenant B', aliases=('shared',), plan=TenantPlan.STARTER))


def test_tenant_context_rejects_blank_tenant_when_required() -> None:
    with pytest.raises(ValueError):
        with bind_tenant_id('   '):
            pass
