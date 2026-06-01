from __future__ import annotations

import pytest

from tenancy.tenant_audit_scope import TenantAuditScope
from tenancy.tenant_billing_scope import TenantBillingScope
from tenancy.tenant_connector_scope import TenantConnectorScope
from tenancy.tenant_contract import TenantRecord
from tenancy.tenant_execution_budget_guard import TenantExecutionBudgetGuard, TenantExecutionUsage
from tenancy.tenant_feature_flags import TenantFeatureFlags
from tenancy.tenant_memory_scope import TenantMemoryScope
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, TenantPolicyBundle
from tenancy.tenant_queue_scope import TenantQueueScope
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_registry import InMemoryTenantRegistry
from tenancy.tenant_runtime_isolation import TenantRuntimeIsolation
from tenancy.tenant_runtime_limits import TenantRuntimeLimits


def _bundle(tenant_id: str) -> TenantPolicyBundle:
    return TenantPolicyBundle(
        tenant_id=tenant_id,
        feature_flags=TenantFeatureFlags(tenant_id=tenant_id),
        runtime_limits=TenantRuntimeLimits(tenant_id=tenant_id, max_concurrent_runs=1, max_actions_per_run=3, max_outbound_messages_per_day=5),
        memory_scope=TenantMemoryScope(tenant_id=tenant_id),
        connector_scope=TenantConnectorScope(tenant_id=tenant_id),
        audit_scope=TenantAuditScope(tenant_id=tenant_id),
        billing_scope=TenantBillingScope(tenant_id=tenant_id),
        quotas={'actions_per_day': 10.0, 'outbound_messages_per_day': 10.0},
    )


def test_runtime_isolation_enforces_single_slot() -> None:
    store = InMemoryTenantPolicyStore((_bundle('acme'),))
    isolation = TenantRuntimeIsolation(policy_store=store)
    first = isolation.acquire(tenant_id='acme', run_id='r1', owner_id='w1')
    assert first.allowed is True
    second = isolation.acquire(tenant_id='acme', run_id='r2', owner_id='w1')
    assert second.allowed is False
    assert second.reason == 'tenant_runtime_concurrency_exceeded'


def test_runtime_isolation_rejects_reacquire_owner_mismatch() -> None:
    store = InMemoryTenantPolicyStore((_bundle('acme'),))
    isolation = TenantRuntimeIsolation(policy_store=store)
    isolation.acquire(tenant_id='acme', run_id='r1', owner_id='w1', labels={'kind': 'exec'})
    with pytest.raises(PermissionError):
        isolation.acquire(tenant_id='acme', run_id='r1', owner_id='w2', labels={'kind': 'exec'})


def test_execution_budget_guard_consumes_without_false_rejection() -> None:
    store = InMemoryTenantPolicyStore((_bundle('acme'),))
    guard = TenantExecutionBudgetGuard(policy_store=store, quota_guard=TenantQuotaGuard(policy_store=store))
    verdict = guard.consume(usage=TenantExecutionUsage(tenant_id='acme', action_count=3, outbound_message_count=2))
    assert verdict.allowed is True
    assert verdict.consumed is True


def test_queue_scope_roundtrip_and_cross_tenant_rejection() -> None:
    scope = TenantQueueScope(tenant_id='acme', queue_name='campaigns')
    key = scope.qualify_job_id('job-1')
    parsed = scope.parse_qualified_key(key)
    assert parsed['tenant_id'] == 'acme'
    assert parsed['queue_name'] == 'campaigns'
    with pytest.raises(ValueError):
        scope.assert_job_mapping({'tenant_id': 'other', 'queue_name': 'campaigns', 'job_id': 'job-1'})


def test_tenant_registry_assert_active_and_register_many() -> None:
    registry = InMemoryTenantRegistry()
    registry.register_many([
        TenantRecord(tenant_id='acme', display_name='Acme'),
        TenantRecord(tenant_id='beta', display_name='Beta'),
    ])
    assert registry.assert_active('acme').tenant_id == 'acme'
    assert len(registry.list_active()) == 2
