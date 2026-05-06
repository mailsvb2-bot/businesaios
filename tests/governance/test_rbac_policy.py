from __future__ import annotations

import pytest

from governance.permission_matrix import PermissionMatrix
from governance.rbac_contract import AccessRequest, ActorContext, Permission, ResourceRef, RoleId
from governance.rbac_policy import RbacPolicy
from governance.role_catalog import RoleCatalog
from governance.tenant_policy_overrides import TenantPolicyOverride, TenantPolicyOverrideRegistry


def build_policy(overrides: TenantPolicyOverrideRegistry | None = None) -> RbacPolicy:
    return RbacPolicy(
        role_catalog=RoleCatalog(),
        permission_matrix=PermissionMatrix(),
        tenant_overrides=overrides,
    )


def test_rbac_policy_allows_owner_budget_change() -> None:
    policy = build_policy()
    request = AccessRequest(
        actor=ActorContext(
            actor_id="owner-1",
            tenant_id="tenant-a",
            role_ids=frozenset({RoleId.OWNER}),
        ),
        permission=Permission.EXECUTE_BUDGET_CHANGE,
        resource=ResourceRef(
            resource_type="action_execution",
            resource_id="exec-1",
            tenant_id="tenant-a",
        ),
        action_name="change_budget",
        metadata={"action_category": "budget_change"},
    )
    verdict = policy.evaluate(request)
    assert verdict.allowed is True
    assert verdict.reason == "allowed"


def test_rbac_policy_blocks_action_even_when_permission_exists_if_tenant_override_blocks() -> None:
    overrides = TenantPolicyOverrideRegistry()
    overrides.put(
        TenantPolicyOverride(
            tenant_id="tenant-a",
            blocked_action_names=frozenset({"dangerous_action"}),
        )
    )
    policy = build_policy(overrides)
    request = AccessRequest(
        actor=ActorContext(
            actor_id="owner-1",
            tenant_id="tenant-a",
            role_ids=frozenset({RoleId.OWNER}),
        ),
        permission=Permission.EXECUTE_STRATEGIC_CHANGE,
        resource=ResourceRef(
            resource_type="action_execution",
            resource_id="exec-1",
            tenant_id="tenant-a",
        ),
        action_name="dangerous_action",
        metadata={"action_category": "strategic_change"},
    )
    verdict = policy.evaluate(request)
    assert verdict.allowed is False
    assert verdict.reason == "blocked_by_tenant_policy_override"


def test_tenant_override_cannot_grant_powerful_permissions() -> None:
    override = TenantPolicyOverride(
        tenant_id="tenant-a",
        add_permissions=frozenset({Permission.EXECUTE_BUDGET_CHANGE}),
    )
    with pytest.raises(ValueError, match="may not grant powerful permissions"):
        override.validate()


def test_cross_tenant_access_request_is_rejected() -> None:
    policy = build_policy()
    request = AccessRequest(
        actor=ActorContext(
            actor_id="owner-1",
            tenant_id="tenant-a",
            role_ids=frozenset({RoleId.OWNER}),
        ),
        permission=Permission.EXECUTE_SAFE_READ,
        resource=ResourceRef(
            resource_type="action_execution",
            resource_id="exec-1",
            tenant_id="tenant-b",
        ),
    )
    with pytest.raises(ValueError, match="cross-tenant access request is forbidden"):
        policy.evaluate(request)
