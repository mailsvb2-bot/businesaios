from __future__ import annotations

from fastapi import Request

from entrypoints.api.request_context import RequestContext


def register_analytics_routes(*, router, analytics_handlers, security_guard) -> None:
    def enforce_public_analytics_security(*, route_path: str, request: Request) -> None:
        request_context = RequestContext.from_http_request(request, metadata={'route': route_path})
        security_guard.enforce(route_path=route_path, request_context=request_context, body=None)

    @router.get('/analytics/business/{tenant_id}')
    def analytics_business_scorecard(tenant_id: str, request: Request, window_days: int = 30) -> dict:
        enforce_public_analytics_security(route_path='/analytics/business/{tenant_id}', request=request)
        return analytics_handlers.get_business_scorecard(tenant_id=tenant_id, window_days=window_days)

    @router.get('/analytics/dashboard/{tenant_id}')
    def analytics_dashboard_bundle(tenant_id: str, request: Request, window_days: int = 30) -> dict:
        enforce_public_analytics_security(route_path='/analytics/dashboard/{tenant_id}', request=request)
        return analytics_handlers.get_dashboard_bundle(tenant_id=tenant_id, window_days=window_days)
