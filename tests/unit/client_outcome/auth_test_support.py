from __future__ import annotations

from entrypoints.api.auth_contract import AuthPrincipal
from governance.rbac_contract import RoleId


class AuthenticatedTestBundle:
    """Minimal authenticated perimeter for client-outcome route unit tests."""

    def authenticate(self, *, request, request_context, authorization, x_api_key) -> AuthPrincipal:
        tenant_id = request_context.tenant_id or request.headers.get('x-tenant-id') or 'tenant-1'
        return AuthPrincipal(
            subject='client-outcome-route-test',
            tenant_id=tenant_id,
            actor_id='client-outcome-route-test',
            roles=(RoleId.SYSTEM,),
            metadata={'auth_type': 'api_key'},
        )
