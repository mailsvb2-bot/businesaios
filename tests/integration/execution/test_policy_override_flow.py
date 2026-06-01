from __future__ import annotations

import pytest
from fastapi import HTTPException

from entrypoints.api.auth_contract import AuthPrincipal
from entrypoints.api.authz_dependencies import AuthzDependencyBundle
from entrypoints.api.rbac_route_guards import RoutePermissionGuard
from entrypoints.api.request_context import RequestContext
from governance.permission_matrix import PermissionMatrix
from governance.rbac_contract import Permission, RoleId
from governance.rbac_policy import RbacPolicy
from governance.role_catalog import RoleCatalog
from governance.tenant_policy_overrides import PersistentTenantPolicyOverrideRegistry, TenantPolicyOverride


def test_policy_override_flow_blocks_then_unblocks_action(tmp_path) -> None:
    overrides = PersistentTenantPolicyOverrideRegistry(path=tmp_path / 'tenant_overrides.json')
    authz = AuthzDependencyBundle(
        rbac_policy=RbacPolicy(role_catalog=RoleCatalog(), permission_matrix=PermissionMatrix(), tenant_overrides=overrides)
    )
    principal = AuthPrincipal(subject='owner', tenant_id='tenant-a', actor_id='owner', roles=(RoleId.OWNER,))
    guard = RoutePermissionGuard(permission=Permission.EXECUTE_PUBLICATION, action_name='publish_landing', action_category='publication')
    context = RequestContext(tenant_id='tenant-a')

    guard.enforce(principal=principal, request_context=context, authz=authz)

    overrides.put(TenantPolicyOverride(tenant_id='tenant-a', blocked_categories=frozenset({'publication'})))
    with pytest.raises(HTTPException) as exc:
        guard.enforce(principal=principal, request_context=context, authz=authz)
    assert exc.value.detail['reason'] == 'blocked_by_tenant_policy_override'

    overrides.remove('tenant-a')
    guard.enforce(principal=principal, request_context=context, authz=authz)


def test_policy_override_flow_persists_and_reloads_registry(tmp_path) -> None:
    path = tmp_path / 'tenant_overrides.json'
    registry = PersistentTenantPolicyOverrideRegistry(path=path)
    registry.put(TenantPolicyOverride(tenant_id='tenant-a', blocked_categories=frozenset({'publication'})))

    reloaded = PersistentTenantPolicyOverrideRegistry(path=path)

    override = reloaded.get('tenant-a')
    assert override is not None
    assert 'publication' in override.blocked_categories
