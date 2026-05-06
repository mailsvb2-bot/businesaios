from __future__ import annotations

from tenancy.tenant_audit_scope import TenantAuditScope
from tenancy.tenant_billing_scope import TenantBillingScope
from tenancy.tenant_connector_scope import TenantConnectorScope
from tenancy.tenant_execution_budget_guard import TenantExecutionBudgetGuard, TenantExecutionUsage
from tenancy.tenant_feature_flags import TenantFeatureFlags
from tenancy.tenant_memory_scope import TenantMemoryScope
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, TenantPolicyBundle
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_runtime_isolation import TenantRuntimeIsolation
from tenancy.tenant_runtime_limits import TenantRuntimeLimits


def _bundle(tenant_id: str = 'acme') -> TenantPolicyBundle:
    return TenantPolicyBundle(
        tenant_id=tenant_id,
        feature_flags=TenantFeatureFlags(tenant_id=tenant_id),
        runtime_limits=TenantRuntimeLimits(tenant_id=tenant_id, max_concurrent_runs=1, max_actions_per_run=5),
        memory_scope=TenantMemoryScope(tenant_id=tenant_id),
        connector_scope=TenantConnectorScope(tenant_id=tenant_id),
        audit_scope=TenantAuditScope(tenant_id=tenant_id),
        billing_scope=TenantBillingScope(tenant_id=tenant_id),
        quotas={'actions_per_day': 5.0, 'outbound_messages_per_day': 5.0},
    )


def test_runtime_isolation_nested_bind_keeps_outer_lease() -> None:
    store = InMemoryTenantPolicyStore((_bundle(),))
    isolation = TenantRuntimeIsolation(policy_store=store)
    with isolation.bind_run(tenant_id='acme', run_id='r1', owner_id='w1'):
        with isolation.bind_run(tenant_id='acme', run_id='r1', owner_id='w1'):
            isolation.assert_isolated(tenant_id='acme', run_id='r1')
        isolation.assert_isolated(tenant_id='acme', run_id='r1')
    assert isolation.inspect(tenant_id='acme').active_runs == 0


def test_quota_guard_consume_many_is_atomic() -> None:
    store = InMemoryTenantPolicyStore((_bundle(),))
    guard = TenantQuotaGuard(policy_store=store)
    verdicts = guard.consume_many(tenant_id='acme', requests=(('actions_per_day', 3.0), ('outbound_messages_per_day', 6.0)))
    assert verdicts['outbound_messages_per_day'].allowed is False
    assert guard.snapshot(tenant_id='acme') == {'actions_per_day': 0.0, 'outbound_messages_per_day': 0.0}


def test_execution_budget_guard_uses_atomic_quota_consume_many() -> None:
    store = InMemoryTenantPolicyStore((_bundle(),))
    guard = TenantExecutionBudgetGuard(policy_store=store, quota_guard=TenantQuotaGuard(policy_store=store))
    verdict = guard.consume(usage=TenantExecutionUsage(tenant_id='acme', action_count=3, outbound_message_count=2))
    assert verdict.allowed is True
    assert verdict.consumed is True



def test_runtime_isolation_release_requires_owner_when_owned() -> None:
    store = InMemoryTenantPolicyStore((_bundle(),))
    isolation = TenantRuntimeIsolation(policy_store=store)
    isolation.acquire(tenant_id='acme', run_id='r1', owner_id='worker-1', labels={})
    try:
        isolation.release(tenant_id='acme', run_id='r1')
        assert False, 'expected PermissionError'
    except PermissionError:
        pass

