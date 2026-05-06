from __future__ import annotations

import pytest

from execution.closed_loop_orchestrator import ClosedLoopCycleInput, ClosedLoopOrchestrator
from tenancy.tenant_audit_scope import TenantAuditScope
from tenancy.tenant_billing_scope import TenantBillingScope
from tenancy.tenant_connector_scope import TenantConnectorScope
from tenancy.tenant_execution_budget_guard import TenantExecutionBudgetGuard
from tenancy.tenant_feature_flags import TenantFeatureFlags
from tenancy.tenant_memory_scope import TenantMemoryScope
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, TenantPolicyBundle
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_runtime_limits import TenantRuntimeLimits


def _guard() -> TenantExecutionBudgetGuard:
    tenant_id = 'acme'
    bundle = TenantPolicyBundle(
        tenant_id=tenant_id,
        feature_flags=TenantFeatureFlags(tenant_id=tenant_id),
        runtime_limits=TenantRuntimeLimits(tenant_id=tenant_id, max_actions_per_run=5),
        memory_scope=TenantMemoryScope(tenant_id=tenant_id),
        connector_scope=TenantConnectorScope(tenant_id=tenant_id),
        audit_scope=TenantAuditScope(tenant_id=tenant_id),
        billing_scope=TenantBillingScope(tenant_id=tenant_id),
        quotas={'actions_per_day': 10.0},
    )
    store = InMemoryTenantPolicyStore((bundle,))
    return TenantExecutionBudgetGuard(policy_store=store, quota_guard=TenantQuotaGuard(policy_store=store))


def test_closed_loop_rejects_cross_tenant_receipt() -> None:
    orchestrator = ClosedLoopOrchestrator()
    with pytest.raises(ValueError):
        orchestrator.run_cycle(
            cycle_input=ClosedLoopCycleInput(
                action={'action_type': 'email', 'tenant_id': 'acme'},
                execution_receipt={'tenant_id': 'other', 'status': 'executed'},
                world_state={'meta': {}},
            )
        )


def test_closed_loop_attaches_tenant_budget_and_scope() -> None:
    orchestrator = ClosedLoopOrchestrator(tenant_execution_budget_guard=_guard())
    result = orchestrator.run_cycle(
        cycle_input=ClosedLoopCycleInput(
            action={'action_type': 'email', 'tenant_id': 'acme', 'queue_name': 'campaigns', 'action_count': 2},
            execution_receipt={'tenant_id': 'acme', 'queue_name': 'campaigns', 'status': 'executed'},
            world_state={'meta': {}},
        )
    )
    assert result.next_tier_context['tenant_scope']['scope_key'] == 'tenant/acme/runtime/queue/campaigns'
    assert result.persisted_memory_evidence['tenant_budget']['allowed'] is True
