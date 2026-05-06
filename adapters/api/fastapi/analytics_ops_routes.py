from __future__ import annotations

from fastapi import Request

from adapters.api.fastapi.router_support import authorize_request, json_body
from entrypoints.api.analytics_models import AnalyticsMaterializeRequest, AnalyticsQueueMaterializeRequest
from entrypoints.api.rbac_route_guards import RoutePermissionGuard
from governance.rbac_contract import Permission


def register_analytics_ops_routes(*, router, analytics_ops_handlers, auth_bundle, authz_bundle, tenant_guard, rate_limit_bundle, security_guard) -> None:
    def _security(*, request: Request, body: dict, tenant_id: str, action_name: str, resource_id: str) -> None:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, body=body, tenant_id=tenant_id)
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(
            principal=principal,
            request_context=request_context,
            authz=authz_bundle,
        )
        security_guard.enforce(
            principal=principal,
            request_context=request_context,
            action_name=action_name,
            tenant_id=tenant_id,
            resource_id=resource_id,
            body=body,
            audit_payload={},
        )
        rate_limit_bundle.require_quota(principal=principal, request_context=request_context, dimension='api_requests_per_hour')

    @router.post('/control-plane/analytics/materialize')
    async def analytics_materialize(request: Request) -> dict:
        body = await json_body(request)
        model = AnalyticsMaterializeRequest(
            tenant_id=str(body.get('tenant_id') or ''),
            window_days=int(body.get('window_days') or 30),
            export_path=body.get('export_path'),
        )
        _security(
            request=request,
            body=body,
            tenant_id=model.tenant_id,
            action_name='api.control_plane.analytics.materialize',
            resource_id=f'analytics-materialize:{model.tenant_id}:{model.window_days}',
        )
        return analytics_ops_handlers.materialize_bundle(model)

    @router.post('/control-plane/analytics/enqueue-materialization')
    async def analytics_enqueue_materialize(request: Request) -> dict:
        body = await json_body(request)
        model = AnalyticsQueueMaterializeRequest(
            tenant_id=str(body.get('tenant_id') or ''),
            window_days=int(body.get('window_days') or 30),
            queue_name=str(body.get('queue_name') or 'analytics'),
            export_path=body.get('export_path'),
        )
        _security(
            request=request,
            body=body,
            tenant_id=model.tenant_id,
            action_name='api.control_plane.analytics.enqueue_materialization',
            resource_id=f'analytics-enqueue:{model.tenant_id}:{model.queue_name}:{model.window_days}',
        )
        return analytics_ops_handlers.enqueue_materialization(model)
