from __future__ import annotations

from fastapi import Request

from adapters.api.fastapi.router_support import authorize_request, json_body
from entrypoints.api.analytics_models import AnalyticsSignedExportRequest
from entrypoints.api.rbac_route_guards import RoutePermissionGuard
from governance.rbac_contract import Permission


def register_analytics_signed_export_routes(*, router, analytics_signed_export_handlers, auth_bundle, authz_bundle, tenant_guard, rate_limit_bundle, security_guard) -> None:
    @router.post('/control-plane/analytics/signed-export')
    async def analytics_signed_export(request: Request) -> dict:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        model = AnalyticsSignedExportRequest(
            tenant_id=str(body.get('tenant_id') or ''),
            export_id=str(body.get('export_id') or ''),
            export_dir=body.get('export_dir'),
            window_days=int(body.get('window_days') or 30),
        )
        tenant_guard.enforce(principal=principal, request_context=request_context, body=body, tenant_id=model.tenant_id)
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name='api.control_plane.analytics.signed_export').enforce(
            principal=principal,
            request_context=request_context,
            authz=authz_bundle,
        )
        security_guard.enforce(
            principal=principal,
            request_context=request_context,
            action_name='api.control_plane.analytics.signed_export',
            tenant_id=model.tenant_id,
            resource_id=f'analytics-signed-export:{model.tenant_id}:{model.export_id}',
            body=body,
            audit_payload={},
        )
        rate_limit_bundle.require_quota(principal=principal, request_context=request_context, dimension='api_requests_per_hour')
        return analytics_signed_export_handlers.export_dashboard_bundle(model)
