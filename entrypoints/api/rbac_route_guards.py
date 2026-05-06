from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from governance.rbac_contract import Permission
from entrypoints.api.auth_contract import AuthPrincipal
from entrypoints.api.authz_dependencies import AuthzDependencyBundle
from entrypoints.api.request_context import RequestContext


CANON_API_RBAC_ROUTE_GUARDS = True
CANON_API_FINAL_OWNER = True


@dataclass(frozen=True)
class RoutePermissionGuard:
    permission: Permission
    action_name: str
    action_category: str | None = None
    resource: Mapping[str, Any] = field(default_factory=dict)

    def enforce(
        self,
        *,
        principal: AuthPrincipal,
        request_context: RequestContext,
        authz: AuthzDependencyBundle,
    ) -> AuthPrincipal:
        authz.require(
            principal=principal,
            request_context=request_context,
            permission=self.permission,
            action_name=self.action_name,
            action_category=self.action_category,
            resource=self.resource,
        )
        return principal


__all__ = [
    'CANON_API_RBAC_ROUTE_GUARDS',
    'RoutePermissionGuard',
]
