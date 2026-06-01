from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from runtime.executor import RuntimeExecutor
from tenancy.tenant_audit_scope import TenantAuditScope
from tenancy.tenant_billing_scope import TenantBillingScope
from tenancy.tenant_connector_scope import TenantConnectorScope
from tenancy.tenant_execution_budget_guard import TenantExecutionBudgetGuard
from tenancy.tenant_feature_flags import TenantFeatureFlags
from tenancy.tenant_memory_scope import TenantMemoryScope
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, TenantPolicyBundle
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_runtime_limits import TenantRuntimeLimits


@dataclass(frozen=True)
class _Decision:
    decision_id: str = "dec-1"
    correlation_id: str = "corr-1"
    action: str = "launch_campaign"
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _Envelope:
    decision: _Decision


class _Guard:
    def execute_once(self, *args: Any, **kwargs: Any) -> None:
        return None


class _Handlers:
    pass


class _Events:
    def append(self, *args: Any, **kwargs: Any) -> None:
        return None


class _PolicyRegistry:
    pass


def _build_executor(runtime_infra: object | None = None, tenant_execution_budget_guard: object | None = None) -> RuntimeExecutor:
    return RuntimeExecutor(guard=_Guard(), handlers=_Handlers(), event_log=_Events(), policy_registry=_PolicyRegistry(), runtime_infra=runtime_infra, tenant_execution_budget_guard=tenant_execution_budget_guard)


def test_runtime_executor_denies_budget_exceeded() -> None:
    executor = _build_executor()
    env = _Envelope(decision=_Decision(action="launch_campaign", payload={"tenant_id": "tenant-1", "autonomy_tier": "full_autonomy", "estimated_cost": 20.0, "economy": {"max_run_cost": 5.0}}))
    with pytest.raises(RuntimeError, match="autonomy_safety_denied:action_budget_exceeded"):
        executor._enforce_runtime_budget_and_blast_radius(env)



def test_runtime_executor_returns_consumed_tenant_budget_verdict() -> None:
    tenant_id = 'tenant-1'
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
    guard = TenantExecutionBudgetGuard(policy_store=store, quota_guard=TenantQuotaGuard(policy_store=store))
    executor = _build_executor(tenant_execution_budget_guard=guard)
    env = _Envelope(decision=_Decision(action='launch_campaign', payload={'tenant_id': tenant_id, 'action_type': 'launch_campaign', 'autonomy_tier': 'full_autonomy', 'approval_policy': {'allow_action_types': ['launch_campaign']}, 'action_count': 2}))
    verdict = executor._enforce_runtime_budget_and_blast_radius(env)
    assert verdict is not None
    assert verdict.allowed is True
    assert verdict.consumed is True
