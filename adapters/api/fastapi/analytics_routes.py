from __future__ import annotations

from fastapi import HTTPException, Request, status

from adapters.api.fastapi.router_support import authorize_request


def register_analytics_routes(*, router, analytics_handlers, security_guard, auth_bundle) -> None:
    def enforce_public_analytics_security(*, route_path: str, request: Request, tenant_id: str) -> None:
        if auth_bundle is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='api_perimeter_auth_unconfigured')
        try:
            request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
            security_guard.enforce(
                route_path=route_path,
                request_context=request_context.with_metadata(route=route_path),
                body={'tenant_id': tenant_id},
                principal=principal,
            )
        except HTTPException:
            raise
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    @router.get('/analytics/business/{tenant_id}')
    def analytics_business_scorecard(tenant_id: str, request: Request, window_days: int = 30) -> dict:
        enforce_public_analytics_security(
            route_path='/analytics/business/{tenant_id}',
            request=request,
            tenant_id=tenant_id,
        )
        return analytics_handlers.get_business_scorecard(tenant_id=tenant_id, window_days=window_days)

    @router.get('/analytics/dashboard/{tenant_id}')
    def analytics_dashboard_bundle(tenant_id: str, request: Request, window_days: int = 30) -> dict:
        enforce_public_analytics_security(
            route_path='/analytics/dashboard/{tenant_id}',
            request=request,
            tenant_id=tenant_id,
        )
        return analytics_handlers.get_dashboard_bundle(tenant_id=tenant_id, window_days=window_days)
