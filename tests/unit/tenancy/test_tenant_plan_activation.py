from __future__ import annotations

from dataclasses import replace

import pytest

from tenancy.tenant_contract import TenantPlan, TenantRecord
from tenancy.tenant_plan_activation import TenantPlanActivationService
from tenancy.tenant_policy_store import (
    InMemoryTenantPolicyStore,
    build_default_tenant_policy_bundle,
)
from tenancy.tenant_registry import InMemoryTenantRegistry, PersistentTenantRegistry


def _growth_policy(tenant_id: str):
    current = build_default_tenant_policy_bundle(tenant_id)
    limits = replace(current.runtime_limits, max_actions_per_run=50)
    quotas = dict(current.quotas)
    quotas["actions_per_day"] = 50.0
    return replace(current, runtime_limits=limits, quotas=quotas)


def test_plan_activation_updates_runtime_policy_and_plan_together() -> None:
    tenant_id = "tenant-a"
    registry = InMemoryTenantRegistry(
        (TenantRecord(tenant_id=tenant_id, display_name="Tenant A", plan=TenantPlan.STARTER),)
    )
    starter_policy = build_default_tenant_policy_bundle(tenant_id)
    policy_store = InMemoryTenantPolicyStore((starter_policy,))
    service = TenantPlanActivationService(
        tenant_registry=registry,
        tenant_policy_store=policy_store,
    )
    target_policy = _growth_policy(tenant_id)

    result = service.activate(
        tenant_id=tenant_id,
        plan=TenantPlan.GROWTH,
        policy=target_policy,
    )

    assert result.changed is True
    assert registry.require(tenant_id).plan is TenantPlan.GROWTH
    assert policy_store.require(tenant_id) == target_policy
    assert policy_store.require(tenant_id).runtime_limits.max_actions_per_run == 50


def test_plan_activation_is_idempotent_for_same_resolved_state() -> None:
    tenant_id = "tenant-a"
    target_policy = _growth_policy(tenant_id)
    registry = InMemoryTenantRegistry(
        (TenantRecord(tenant_id=tenant_id, display_name="Tenant A", plan=TenantPlan.GROWTH),)
    )
    policy_store = InMemoryTenantPolicyStore((target_policy,))
    service = TenantPlanActivationService(
        tenant_registry=registry,
        tenant_policy_store=policy_store,
    )

    result = service.activate(
        tenant_id=tenant_id,
        plan=TenantPlan.GROWTH,
        policy=target_policy,
    )

    assert result.changed is False
    assert result.record.plan is TenantPlan.GROWTH
    assert result.policy == target_policy


def test_plan_activation_rejects_cross_tenant_policy() -> None:
    registry = InMemoryTenantRegistry(
        (TenantRecord(tenant_id="tenant-a", display_name="Tenant A"),)
    )
    policy_store = InMemoryTenantPolicyStore((build_default_tenant_policy_bundle("tenant-a"),))
    service = TenantPlanActivationService(
        tenant_registry=registry,
        tenant_policy_store=policy_store,
    )

    with pytest.raises(ValueError, match="cross-tenant"):
        service.activate(
            tenant_id="tenant-a",
            plan=TenantPlan.GROWTH,
            policy=_growth_policy("tenant-b"),
        )


class _FailingGrowthRegistry(InMemoryTenantRegistry):
    def set_plan(self, *, tenant_id: str, plan: TenantPlan):
        if plan is TenantPlan.GROWTH:
            raise RuntimeError("registry write failed")
        return super().set_plan(tenant_id=tenant_id, plan=plan)


def test_plan_activation_rolls_policy_back_when_plan_write_fails() -> None:
    tenant_id = "tenant-a"
    registry = _FailingGrowthRegistry(
        (TenantRecord(tenant_id=tenant_id, display_name="Tenant A", plan=TenantPlan.STARTER),)
    )
    starter_policy = build_default_tenant_policy_bundle(tenant_id)
    policy_store = InMemoryTenantPolicyStore((starter_policy,))
    service = TenantPlanActivationService(
        tenant_registry=registry,
        tenant_policy_store=policy_store,
    )

    with pytest.raises(RuntimeError, match="registry write failed"):
        service.activate(
            tenant_id=tenant_id,
            plan=TenantPlan.GROWTH,
            policy=_growth_policy(tenant_id),
        )

    assert registry.require(tenant_id).plan is TenantPlan.STARTER
    assert policy_store.require(tenant_id) == starter_policy


def test_persistent_registry_persists_plan_updates(tmp_path) -> None:
    path = tmp_path / "tenants.json"
    registry = PersistentTenantRegistry(path=path)
    registry.register(TenantRecord(tenant_id="tenant-a", display_name="Tenant A"))

    registry.set_plan(tenant_id="tenant-a", plan=TenantPlan.GROWTH)

    reloaded = PersistentTenantRegistry(path=path)
    assert reloaded.require("tenant-a").plan is TenantPlan.GROWTH
