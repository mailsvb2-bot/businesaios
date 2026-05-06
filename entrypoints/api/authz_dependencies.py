from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from fastapi import HTTPException, status

from governance.permission_matrix import PermissionMatrix
from governance.rbac_contract import AccessRequest, ActorContext, Permission, ResourceRef
from governance.rbac_policy import RbacPolicy
from governance.role_catalog import RoleCatalog
from entrypoints.api.auth_contract import AuthPrincipal
from entrypoints.api.request_context import RequestContext


CANON_API_AUTHZ_DEPENDENCIES = True
CANON_API_FINAL_OWNER = True


@dataclass(frozen=True)
class AuthzDependencyBundle:
    rbac_policy: RbacPolicy

    @classmethod
    def default(cls) -> 'AuthzDependencyBundle':
        return cls(
            rbac_policy=RbacPolicy(
                role_catalog=RoleCatalog(),
                permission_matrix=PermissionMatrix(),
            )
        )

    def require(
        self,
        *,
        principal: AuthPrincipal,
        request_context: RequestContext,
        permission: Permission,
        action_name: str,
        action_category: str | None = None,
        resource: Mapping[str, Any] | None = None,
    ) -> None:
        tenant_id = principal.tenant_id or request_context.validated_tenant_id(required=True)
        resource_ref = _resource_ref(resource=resource, tenant_id=tenant_id)
        verdict = self.rbac_policy.evaluate(
            AccessRequest(
                actor=ActorContext(
                    actor_id=principal.actor_id or principal.subject,
                    tenant_id=tenant_id,
                    role_ids=frozenset(principal.roles),
                    is_service=str(principal.metadata.get('principal_kind') or '') == 'service',
                    attributes={
                        'subject': principal.subject,
                        'scopes': list(principal.scopes),
                    },
                ),
                permission=permission,
                resource=resource_ref,
                action_name=action_name,
                metadata={'action_category': action_category or ''},
            )
        )
        if not verdict.allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    'reason': verdict.reason,
                    'permission': permission.value,
                    'action_name': action_name,
                    'operator_required': verdict.operator_required,
                },
            )


def _resource_ref(*, resource: Mapping[str, Any] | None, tenant_id: str) -> ResourceRef | None:
    payload = dict(resource or {})
    resource_type = str(payload.get('resource_type') or '').strip()
    resource_id = str(payload.get('resource_id') or '').strip()
    if not resource_type or not resource_id:
        return None
    resource_tenant_id = str(payload.get('tenant_id') or tenant_id).strip()
    return ResourceRef(
        resource_type=resource_type,
        resource_id=resource_id,
        tenant_id=resource_tenant_id,
        attributes={k: v for k, v in payload.items() if k not in {'resource_type', 'resource_id', 'tenant_id'}},
    )


def require_permission(
    bundle: AuthzDependencyBundle,
    permission: Permission,
    *,
    action_name: str,
    action_category: str | None = None,
    resource: Mapping[str, Any] | None = None,
) -> Callable[[AuthPrincipal, RequestContext], AuthPrincipal]:
    def _dependency(principal: AuthPrincipal, request_context: RequestContext) -> AuthPrincipal:
        bundle.require(
            principal=principal,
            request_context=request_context,
            permission=permission,
            action_name=action_name,
            action_category=action_category,
            resource=resource,
        )
        return principal
    return _dependency


__all__ = [
    'AuthzDependencyBundle',
    'CANON_API_AUTHZ_DEPENDENCIES',
    'require_permission',
]
