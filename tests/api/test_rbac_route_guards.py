from __future__ import annotations

import pytest
from fastapi import HTTPException

from governance.permission_matrix import PermissionMatrix
from governance.rbac_contract import Permission, RoleId
from governance.rbac_policy import RbacPolicy
from governance.role_catalog import RoleCatalog
from entrypoints.api.auth_contract import AuthPrincipal
from entrypoints.api.authz_dependencies import AuthzDependencyBundle
from entrypoints.api.rbac_route_guards import RoutePermissionGuard
from entrypoints.api.request_context import RequestContext


def _bundle() -> AuthzDependencyBundle:
    return AuthzDependencyBundle(rbac_policy=RbacPolicy(role_catalog=RoleCatalog(), permission_matrix=PermissionMatrix()))


def test_rbac_route_guard_allows_authorized_principal() -> None:
    principal = AuthPrincipal(subject='alice', tenant_id='tenant-a', actor_id='alice', roles=(RoleId.OWNER,))
    guard = RoutePermissionGuard(permission=Permission.VIEW_AUDIT, action_name='view_audit')

    result = guard.enforce(principal=principal, request_context=RequestContext(tenant_id='tenant-a'), authz=_bundle())

    assert result.subject == 'alice'


def test_rbac_route_guard_denies_missing_permission() -> None:
    principal = AuthPrincipal(subject='viewer', tenant_id='tenant-a', actor_id='viewer', roles=(RoleId.VIEWER,))
    guard = RoutePermissionGuard(permission=Permission.EXECUTE_OUTBOUND, action_name='send_campaign', action_category='outbound')

    with pytest.raises(HTTPException) as exc:
        guard.enforce(principal=principal, request_context=RequestContext(tenant_id='tenant-a'), authz=_bundle())

    assert exc.value.status_code == 403
    assert exc.value.detail['reason'] == 'missing_permission'


def test_rbac_route_guard_denies_cross_tenant_resource_reference_fail_closed() -> None:
    principal = AuthPrincipal(subject='owner', tenant_id='tenant-a', actor_id='owner', roles=(RoleId.OWNER,))
    authz = _bundle()

    with pytest.raises(ValueError, match='cross-tenant access request is forbidden'):
        authz.require(
            principal=principal,
            request_context=RequestContext(tenant_id='tenant-a'),
            permission=Permission.VIEW_AUDIT,
            action_name='view_resource',
            resource={'resource_type': 'tenant', 'resource_id': 'x', 'tenant_id': 'tenant-b'},
        )
