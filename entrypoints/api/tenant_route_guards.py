from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from fastapi import HTTPException, status

from core.tenancy.normalization import normalize_tenant_id
from entrypoints.api.auth_contract import AuthPrincipal
from entrypoints.api.request_context import RequestContext
from entrypoints.api.security_surface_guard import ApiSecuritySurfaceGuard
from tenancy.tenant_contract import TenantStatus
from tenancy.tenant_registry import InMemoryTenantRegistry

from security.access_policy import SecurityAction


CANON_API_TENANT_ROUTE_GUARDS = True
CANON_API_FINAL_OWNER = True


@dataclass(frozen=True, kw_only=True)
class TenantRouteGuard:
    require_principal_tenant: bool = True
    require_request_tenant: bool = True
    tenant_registry: InMemoryTenantRegistry | None = None
    require_active_tenant: bool = False
    security_guard: ApiSecuritySurfaceGuard

    def enforce(
        self,
        *,
        principal: AuthPrincipal,
        request_context: RequestContext,
        tenant_id: str | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> str:
        context_tenant = request_context.validated_tenant_id(required=self.require_request_tenant)
        principal_tenant = normalize_tenant_id(principal.tenant_id)
        payload_tenant = _extract_tenant_id(body)
        path_tenant = normalize_tenant_id(tenant_id)
        expected = path_tenant or payload_tenant or context_tenant or principal_tenant
        if not expected:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='missing_tenant_id')
        for candidate_name, candidate_value in (
            ('principal', principal_tenant),
            ('request', context_tenant),
            ('payload', payload_tenant),
            ('path', path_tenant),
        ):
            if candidate_value and candidate_value != expected:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f'tenant_mismatch:{candidate_name}',
                )
        if self.require_principal_tenant and principal_tenant is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='principal_tenant_required')
        if self.tenant_registry is not None:
            record = self.tenant_registry.lookup(expected)
            if record is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='unknown_tenant')
            if self.require_active_tenant and record.status is not TenantStatus.ACTIVE:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='inactive_tenant')
        try:
            self.security_guard.enforce(
                principal=principal,
                request_context=request_context,
                resource_type='tenant_boundary',
                resource_id=expected,
                action=SecurityAction.ADMIN if self.require_active_tenant else SecurityAction.READ,
                surface='api_tenant_guard',
                classification_input={
                    'name': 'tenant boundary policy',
                    'tags': ('internal', 'tenant', 'policy', 'token'),
                },
                audit_payload={'guard': 'tenant_route', 'tenant_id': expected},
            )
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        return expected


def _extract_tenant_id(body: Mapping[str, Any] | None) -> str | None:
    payload = dict(body or {})
    return normalize_tenant_id(payload.get('tenant_id'))


__all__ = [
    'CANON_API_TENANT_ROUTE_GUARDS',
    'TenantRouteGuard',
]
