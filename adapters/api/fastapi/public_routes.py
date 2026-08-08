from __future__ import annotations

import inspect
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status

from adapters.api.fastapi.analytics_routes import register_analytics_routes
from adapters.api.fastapi.business_workspace_provider_routes import register_business_workspace_provider_routes
from adapters.api.fastapi.public_client_outcome_routes import register_public_client_outcome_routes
from adapters.api.fastapi.public_core_routes import register_public_core_routes
from adapters.api.fastapi.public_site_routes import (
    _cta_status_response,
    _cta_submit_response,
    register_public_site_routes,
)
from adapters.api.fastapi.router_support import authorize_request
from entrypoints.api.public_surface_security_guard import PublicSurfaceSecurityGuard
from entrypoints.api.request_context import RequestContext


CANON_FASTAPI_PUBLIC_ROUTES_FINAL_OWNER = True
CANON_PRODUCTION_GUARD_PRINCIPAL_CONTRACT_REQUIRED = True


def _is_test_guard(security_guard: PublicSurfaceSecurityGuard) -> bool:
    source_file = inspect.getsourcefile(type(security_guard))
    if not source_file:
        return False
    return 'tests' in Path(source_file).resolve().parts


def _enforce_security_guard(
    *,
    security_guard: PublicSurfaceSecurityGuard,
    route_path: str,
    request_context: RequestContext,
    body: dict | None,
    principal,
) -> None:
    enforce_parameters = inspect.signature(security_guard.enforce).parameters
    if 'principal' in enforce_parameters:
        security_guard.enforce(
            route_path=route_path,
            request_context=request_context,
            body=body,
            principal=principal,
        )
        return
    if not _is_test_guard(security_guard):
        raise PermissionError('api_security_guard_principal_contract_required')
    security_guard.enforce(
        route_path=route_path,
        request_context=request_context,
        body=body,
    )


def register_public_api_routes(
    *,
    router: APIRouter,
    dependency_container,
    health_handler,
    handlers,
    headless_handlers,
    governance_handlers,
    business_memory_handlers,
    governance_advanced_handlers,
    security_guard: PublicSurfaceSecurityGuard,
    auth_bundle=None,
    tenant_registry=None,
    analytics_handlers=None,
    client_outcome_handlers=None,
    economic_handlers=None,
) -> None:
    if tenant_registry is None and dependency_container is not None:
        tenant_registry = getattr(dependency_container, 'tenant_registry', None)

    def enforce_public_security(
        *,
        route_path: str,
        request_context: RequestContext,
        body: dict | None = None,
        http_request: Request | None = None,
    ) -> RequestContext:
        try:
            principal = None
            if security_guard.requires_external_auth(route_path):
                if auth_bundle is None:
                    raise PermissionError('api_perimeter_auth_unconfigured')
                if http_request is None:
                    raise PermissionError('api_perimeter_request_required')
                request_context, principal = authorize_request(request=http_request, auth_bundle=auth_bundle)
                request_context = request_context.with_metadata(route=route_path)
            _enforce_security_guard(
                security_guard=security_guard,
                route_path=route_path,
                request_context=request_context,
                body=body,
                principal=principal,
            )
        except HTTPException:
            raise
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        return request_context

    def authenticated_tenant(request_context: RequestContext) -> str:
        tenant_id = request_context.validated_tenant_id(required=True)
        assert tenant_id is not None
        return tenant_id

    def raise_boundary_error(exc: Exception) -> None:
        if isinstance(exc, PermissionError):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        if isinstance(exc, KeyError):
            detail = str(exc.args[0] if exc.args else 'not_found')
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        raise exc

    register_public_core_routes(
        router=router,
        health_handler=health_handler,
        handlers=handlers,
        headless_handlers=headless_handlers,
        governance_handlers=governance_handlers,
        business_memory_handlers=business_memory_handlers,
        governance_advanced_handlers=governance_advanced_handlers,
        enforce_public_security=enforce_public_security,
    )
    register_public_site_routes(router=router, enforce_public_security=enforce_public_security, auth_bundle=auth_bundle, tenant_registry=tenant_registry)
    if auth_bundle is not None:
        register_business_workspace_provider_routes(router=router, auth_bundle=auth_bundle)
    register_public_client_outcome_routes(
        router=router,
        client_outcome_handlers=client_outcome_handlers,
        economic_handlers=economic_handlers,
        enforce_public_security=enforce_public_security,
        authenticated_tenant=authenticated_tenant,
        raise_boundary_error=raise_boundary_error,
    )
    if analytics_handlers is not None:
        register_analytics_routes(
            router=router,
            analytics_handlers=analytics_handlers,
            security_guard=security_guard,
            auth_bundle=auth_bundle,
        )


__all__ = [
    'CANON_FASTAPI_PUBLIC_ROUTES_FINAL_OWNER',
    'CANON_PRODUCTION_GUARD_PRINCIPAL_CONTRACT_REQUIRED',
    '_cta_status_response',
    '_cta_submit_response',
    'register_public_api_routes',
]
