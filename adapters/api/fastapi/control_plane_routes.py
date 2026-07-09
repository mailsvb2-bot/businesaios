"""Final owner: adapters.api.fastapi.control_plane_routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from adapters.api.fastapi.analytics_ops_routes import register_analytics_ops_routes
from adapters.api.fastapi.analytics_signed_export_routes import register_analytics_signed_export_routes
from adapters.api.fastapi.router_support import authorize_request, first_role, json_body, tenant_if_present
from entrypoints.api.control_plane_security_guard import ControlPlaneSecurityGuard
from entrypoints.api.rbac_route_guards import RoutePermissionGuard
from entrypoints.api.request_context import RequestContext
from governance.approval_contract import ApprovalOutcome
from governance.rbac_contract import Permission, RoleId

CANON_FASTAPI_CONTROL_PLANE_ROUTES_FINAL_OWNER = True


def register_control_plane_routes(*, router: APIRouter, auth_bundle, authz_bundle, tenant_guard, rate_limit_bundle, audit_handlers, approval_handlers, admin_handlers, connector_admin_handlers, provider_admin_handlers, metrics_handlers, webhook_handlers, queue_ops_handlers, security_guard: ControlPlaneSecurityGuard, analytics_ops_handlers=None, analytics_signed_export_handlers=None) -> None:

    def enforce_control_plane_security(*, principal, request_context, action_name: str, tenant_id: str | None, resource_id: str, body: dict[str, Any] | None = None, **audit_payload: Any) -> dict[str, Any]:
        try:
            return security_guard.enforce(
                principal=principal,
                request_context=request_context,
                action_name=action_name,
                tenant_id=tenant_id,
                resource_id=resource_id,
                body=body,
                audit_payload=audit_payload,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    @router.get('/control-plane/audit/actions')
    async def control_plane_list_action_audit(request: Request, trace_id: str | None = None, limit: int = 100) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_id = tenant_if_present(principal=principal, request_context=request_context, tenant_guard=tenant_guard, body=None)
        action_name = 'api.control_plane.audit.actions'
        RoutePermissionGuard(permission=Permission.VIEW_AUDIT, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'audit-actions:{trace_id or "all"}', trace_id=trace_id, limit=limit)
        rate_limit_bundle.require_quota(principal=principal, request_context=request_context, dimension='api_requests_per_hour')
        return audit_handlers.list_actions(trace_id=trace_id, limit=limit)

    @router.get('/control-plane/audit/decisions')
    async def control_plane_list_decision_audit(request: Request, trace_id: str | None = None, limit: int = 100) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_id = tenant_if_present(principal=principal, request_context=request_context, tenant_guard=tenant_guard, body=None)
        action_name = 'api.control_plane.audit.decisions'
        RoutePermissionGuard(permission=Permission.VIEW_AUDIT, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'audit-decisions:{trace_id or "all"}', trace_id=trace_id, limit=limit)
        rate_limit_bundle.require_quota(principal=principal, request_context=request_context, dimension='api_requests_per_hour')
        return audit_handlers.list_decisions(trace_id=trace_id, limit=limit)

    @router.get('/control-plane/approvals/open')
    async def control_plane_list_open_approvals(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_id = tenant_guard.enforce(principal=principal, request_context=request_context, body=None)
        action_name = 'api.control_plane.approvals.list_open'
        RoutePermissionGuard(permission=Permission.VIEW_APPROVALS, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'approval-open:{tenant_id}')
        return approval_handlers.list_open(tenant_id=tenant_id)

    @router.post('/control-plane/approvals/submit')
    async def control_plane_submit_approval(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        tenant_id = tenant_guard.enforce(principal=principal, request_context=request_context, body=body)
        action_name = 'api.control_plane.approvals.submit'
        RoutePermissionGuard(permission=Permission.APPROVE_CHANGE, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'approval-submit:{tenant_id}:{body.get("subject_type") or "unknown"}:{body.get("subject_id") or "unknown"}', body=body)
        role_groups = tuple(tuple(RoleId(str(role)) for role in group) for group in body.get('required_role_groups', []))
        return approval_handlers.submit(tenant_id=tenant_id, subject_type=str(body.get('subject_type') or ''), subject_id=str(body.get('subject_id') or ''), requested_by=principal.actor_id or principal.subject, reason=str(body.get('reason') or ''), required_role_groups=role_groups, min_distinct_approvers=int(body.get('min_distinct_approvers', 1) or 1), prohibit_self_approval=bool(body.get('prohibit_self_approval', True)), metadata={'via': 'api.control-plane', 'request_id': request_context.normalized_request_id()})

    @router.post('/control-plane/approvals/{approval_id}/decide')
    async def control_plane_decide_approval(approval_id: str, request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        tenant_id = tenant_guard.enforce(principal=principal, request_context=request_context, body=body)
        action_name = 'api.control_plane.approvals.decide'
        RoutePermissionGuard(permission=Permission.APPROVE_CHANGE, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'approval-decision:{tenant_id}:{approval_id}', body=body, approval_id=approval_id)
        role_id = first_role(principal)
        outcome = ApprovalOutcome(str(body.get('outcome') or 'approve'))
        return approval_handlers.evaluate(approval_id=approval_id, tenant_id=tenant_id, actor_id=principal.actor_id or principal.subject, role_id=role_id, outcome=outcome, rationale=str(body.get('rationale') or ''), metadata={'via': 'api.control-plane', 'request_id': request_context.normalized_request_id()})

    @router.get('/control-plane/admin/tenants')
    async def control_plane_list_active_tenants(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        action_name = 'api.control_plane.admin.list_tenants'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=principal.tenant_id, resource_id='tenant-registry')
        return admin_handlers.list_active_tenants()

    @router.get('/control-plane/admin/tenant-policy/{tenant_id}')
    async def control_plane_get_tenant_policy(tenant_id: str, request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.admin.get_tenant_policy'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'tenant-policy:{tenant_id}')
        return admin_handlers.get_tenant_policy(tenant_id=tenant_id)


    @router.get('/control-plane/admin/platform-overview')
    async def control_plane_platform_overview(request: Request, tenant_id: str = 'tenant-demo', business_id: str = 'default-business') -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.admin.platform_overview'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'platform-overview:{tenant_id}:{business_id}')
        return admin_handlers.get_platform_overview(tenant_id=tenant_id, business_id=business_id)

    @router.get('/control-plane/admin/platform-risks')
    async def control_plane_platform_risks(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        action_name = 'api.control_plane.admin.platform_risks'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=principal.tenant_id, resource_id='platform-risk-registry')
        return admin_handlers.get_platform_risk_registry()

    @router.get('/control-plane/admin/platform-dependencies')
    async def control_plane_platform_dependencies(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        action_name = 'api.control_plane.admin.platform_dependencies'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=principal.tenant_id, resource_id='platform-dependencies')
        return admin_handlers.get_platform_dependency_graph()

    @router.get('/control-plane/admin/platform-remediation')
    async def control_plane_platform_remediation(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        action_name = 'api.control_plane.admin.platform_remediation'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=principal.tenant_id, resource_id='platform-remediation')
        return admin_handlers.get_platform_remediation_plan()

    @router.get('/control-plane/admin/platform-risk-diff')
    async def control_plane_platform_risk_diff(request: Request, tenant_id: str = 'tenant-demo') -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.admin.platform_risk_diff'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'platform-risk-diff:{tenant_id}')
        return admin_handlers.get_platform_risk_diff(tenant_id=tenant_id)


    @router.get('/control-plane/admin/platform-ownership')
    async def control_plane_platform_ownership(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        action_name = 'api.control_plane.admin.platform_ownership'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=principal.tenant_id, resource_id='platform-ownership')
        return admin_handlers.get_platform_ownership_graph()

    @router.get('/control-plane/admin/platform-patch-suggestions')
    async def control_plane_platform_patch_suggestions(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        action_name = 'api.control_plane.admin.platform_patch_suggestions'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=principal.tenant_id, resource_id='platform-patch-suggestions')
        return admin_handlers.get_platform_patch_suggestions()

    @router.get('/control-plane/admin/platform-snapshot-diff-view')
    async def control_plane_platform_snapshot_diff_view(request: Request, tenant_id: str = 'tenant-demo') -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.admin.platform_snapshot_diff_view'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'platform-snapshot-diff-view:{tenant_id}')
        return admin_handlers.get_platform_snapshot_diff_view(tenant_id=tenant_id)

    @router.get('/control-plane/admin/platform-file-passport')
    async def control_plane_platform_file_passport(request: Request, file_path: str) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        action_name = 'api.control_plane.admin.platform_file_passport'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=principal.tenant_id, resource_id=f'platform-file-passport:{file_path}')
        return admin_handlers.get_platform_file_passport(file_path=file_path)

    @router.get('/control-plane/admin/platform-ownership-drilldown')
    async def control_plane_platform_ownership_drilldown(request: Request, block: str) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        action_name = 'api.control_plane.admin.platform_ownership_drilldown'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=principal.tenant_id, resource_id=f'platform-ownership-drilldown:{block}')
        return admin_handlers.get_platform_ownership_drilldown(block=block)

    @router.get('/control-plane/admin/platform-risk-trends')
    async def control_plane_platform_risk_trends(request: Request, tenant_id: str = 'tenant-demo') -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.admin.platform_risk_trends'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'platform-risk-trends:{tenant_id}')
        return admin_handlers.get_platform_risk_trends(tenant_id=tenant_id)

    @router.get('/control-plane/admin/platform-maturity-trends')
    async def control_plane_platform_maturity_trends(request: Request, tenant_id: str = 'tenant-demo') -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.admin.platform_maturity_trends'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'platform-maturity-trends:{tenant_id}')
        return admin_handlers.get_platform_maturity_trends(tenant_id=tenant_id)

    @router.get('/control-plane/admin/platform-stop-conditions')
    async def control_plane_platform_stop_conditions(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        action_name = 'api.control_plane.admin.platform_stop_conditions'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=principal.tenant_id, resource_id='platform-stop-conditions')
        return admin_handlers.get_platform_stop_conditions()

    @router.get('/control-plane/admin/platform-widget-runtime')
    async def control_plane_platform_widget_runtime(request: Request, tenant_id: str = 'tenant-demo', business_id: str = 'default-business') -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.admin.platform_widget_runtime'
        RoutePermissionGuard(permission=Permission.VIEW_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'platform-widget-runtime:{tenant_id}:{business_id}', business_id=business_id)
        return admin_handlers.get_platform_widget_runtime(tenant_id=tenant_id, business_id=business_id)

    @router.get('/control-plane/admin/platform-live-widgets')
    async def control_plane_platform_live_widgets(request: Request, tenant_id: str = 'tenant-demo', business_id: str = 'default-business') -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.admin.platform_live_widgets'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'platform-live-widgets:{tenant_id}:{business_id}')
        return admin_handlers.get_platform_live_widgets(tenant_id=tenant_id, business_id=business_id)

    @router.get('/control-plane/admin/platform-visual-conflicts')
    async def control_plane_platform_visual_conflicts(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        action_name = 'api.control_plane.admin.platform_visual_conflicts'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=principal.tenant_id, resource_id='platform-visual-conflicts')
        return admin_handlers.get_platform_visual_conflicts()

    @router.post('/control-plane/admin/platform-dashboard-layout')
    async def control_plane_platform_dashboard_layout(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        tenant_id = tenant_guard.enforce(principal=principal, request_context=request_context, body=body)
        action_name = 'api.control_plane.admin.platform_dashboard_layout'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        layout = dict(body.get('layout') or {})
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'platform-dashboard-layout:{tenant_id}', body={'layout': layout})
        return admin_handlers.save_platform_dashboard_layout(tenant_id=tenant_id, layout=layout)

    @router.get('/control-plane/admin/platform-remediation-workflow')
    async def control_plane_platform_remediation_workflow(request: Request, file_path: str, risk_type: str = '') -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        action_name = 'api.control_plane.admin.platform_remediation_workflow'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=principal.tenant_id, resource_id=f'platform-remediation-workflow:{file_path}')
        return admin_handlers.get_platform_remediation_workflow(file_path=file_path, risk_type=risk_type)

    @router.post('/control-plane/admin/platform-remediation-run')
    async def control_plane_platform_remediation_run(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        file_path = str(body.get('file_path') or '').strip()
        risk_type = str(body.get('risk_type') or '').strip()
        action_name = 'api.control_plane.admin.platform_remediation_run'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=principal.tenant_id, resource_id=f'platform-remediation-run:{file_path}', body={'file_path': file_path, 'risk_type': risk_type})
        return admin_handlers.run_platform_remediation(file_path=file_path, risk_type=risk_type)

    @router.get('/control-plane/metrics/global')
    async def control_plane_metrics_global(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        action_name = 'api.control_plane.metrics.global'
        RoutePermissionGuard(permission=Permission.VIEW_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=principal.tenant_id, resource_id='platform-metrics')
        return metrics_handlers.global_snapshot()

    @router.get('/control-plane/metrics/tenant/{tenant_id}')
    async def control_plane_metrics_tenant(tenant_id: str, request: Request, window_seconds: int | None = None) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.metrics.tenant'
        RoutePermissionGuard(permission=Permission.VIEW_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'tenant-metrics:{tenant_id}', audit_window_seconds=window_seconds)
        return metrics_handlers.tenant_snapshot(tenant_id=tenant_id, window_seconds=window_seconds)


    @router.get('/control-plane/provider-admin/catalog')
    async def control_plane_provider_catalog(request: Request, tenant_id: str, business_id: str) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.provider_admin.catalog'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'provider-admin-catalog:{tenant_id}:{business_id}', business_id=business_id)
        return provider_admin_handlers.list_provider_catalog(tenant_id=tenant_id, business_id=business_id)

    @router.get('/control-plane/provider-admin/secret-history')
    async def control_plane_provider_secret_history(request: Request, tenant_id: str, business_id: str, provider_key: str) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.provider_admin.secret_history'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'provider-admin-secret-history:{tenant_id}:{business_id}:{provider_key}')
        return provider_admin_handlers.list_provider_secret_history(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key)

    @router.post('/control-plane/provider-admin/secret-rollback')
    async def control_plane_provider_secret_rollback(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        tenant_id = tenant_guard.enforce(principal=principal, request_context=request_context, body=body)
        action_name = 'api.control_plane.provider_admin.secret_rollback'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f"provider-admin-secret-rollback:{tenant_id}:{body.get('business_id') or 'unknown'}:{body.get('provider_key') or 'unknown'}:{body.get('secret_name') or 'unknown'}", body=body)
        return provider_admin_handlers.rollback_provider_secret(payload=body)


    @router.post('/control-plane/provider-admin/mark-compromised')
    async def control_plane_provider_admin_mark_compromised(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        tenant_id = tenant_guard.enforce(principal=principal, request_context=request_context, body=body)
        business_id = str(body.get('business_id') or '').strip() or 'default-business'
        provider_key = str(body.get('provider_key') or '').strip()
        action_name = 'api.control_plane.provider_admin.mark_compromised'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'provider-mark-compromised:{provider_key}', business_id=business_id, body=body)
        return provider_admin_handlers.mark_provider_secret_compromised(payload={**body, 'tenant_id': tenant_id})

    @router.post('/control-plane/provider-runtime/schedule-retry')
    async def control_plane_provider_runtime_schedule_retry(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        tenant_id = tenant_guard.enforce(principal=principal, request_context=request_context, body=body)
        business_id = str(body.get('business_id') or '').strip() or 'default-business'
        provider_key = str(body.get('provider_key') or '').strip()
        action_name = 'api.control_plane.provider_runtime.schedule_retry'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'provider-schedule-retry:{provider_key}', business_id=business_id, body=body)
        return provider_admin_handlers.schedule_provider_retry(payload={**body, 'tenant_id': tenant_id})

    @router.get('/control-plane/provider-runtime/retry-jobs')
    async def control_plane_provider_runtime_retry_jobs(request: Request, tenant_id: str, business_id: str, provider_key: str, limit: int = 20) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.provider_runtime_retry_jobs'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'provider-runtime-retry-jobs:{tenant_id}:{business_id}:{provider_key}', business_id=business_id)
        return provider_admin_handlers.list_provider_retry_jobs(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, limit=limit)

    @router.get('/control-plane/provider-runtime/export-history')
    async def control_plane_provider_runtime_export_history(request: Request, tenant_id: str, business_id: str, provider_key: str, limit: int = 20) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.provider_runtime_export_history'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'provider-runtime-export-history:{tenant_id}:{business_id}:{provider_key}', business_id=business_id)
        return provider_admin_handlers.list_provider_export_history(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, limit=limit)

    @router.get('/control-plane/provider-runtime/routes')
    async def control_plane_provider_runtime_routes(request: Request, provider_key: str) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        action_name = 'api.control_plane.provider_runtime.routes'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=principal.tenant_id, resource_id=f'provider-runtime-routes:{provider_key}')
        return provider_admin_handlers.get_provider_runtime_routes(provider_key=provider_key)

    @router.post('/providers/webhook/{tenant_id}/{business_id}/{provider_key}')
    async def public_provider_webhook_ingest(tenant_id: str, business_id: str, provider_key: str, request: Request) -> dict[str, Any]:
        body = await request.body()
        headers = {str(k): str(v) for k, v in request.headers.items()}
        event_key = str(headers.get('X-Event-Id') or headers.get('X-Shopify-Webhook-Id') or headers.get('X-Request-Id') or '').strip()
        topic = str(headers.get('X-Topic') or headers.get('X-Shopify-Topic') or headers.get('X-Webhook-Topic') or '').strip()
        if not event_key:
            event_key = request.headers.get('x-amz-request-id', '') or request.headers.get('cf-ray', '') or 'payload-digest-fallback'
        return provider_admin_handlers.ingest_provider_webhook(payload={'tenant_id': tenant_id, 'business_id': business_id, 'provider_key': provider_key, 'headers': headers, 'body': body.decode('utf-8', errors='ignore'), 'event_key': event_key, 'topic': topic, 'owner_id': 'public_provider_webhook'})

    @router.post('/control-plane/provider-admin/activate')
    async def control_plane_provider_activate(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        tenant_id = tenant_guard.enforce(principal=principal, request_context=request_context, body=body)
        action_name = 'api.control_plane.provider_admin.activate'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        body = {**body, 'tenant_id': tenant_id, 'requested_by': body.get('requested_by') or principal.actor_id or principal.subject}
        resource_id = f"provider-admin-activate:{tenant_id}:{body.get('business_id') or 'unknown'}:{body.get('provider_key') or 'unknown'}"
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=resource_id, body={k: ('***' if k == 'secrets' else v) for k, v in body.items()})
        return provider_admin_handlers.activate_provider(payload=body)


    @router.post('/control-plane/provider-admin/rotate')
    async def control_plane_provider_rotate(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        tenant_id = tenant_guard.enforce(principal=principal, request_context=request_context, body=body)
        action_name = 'api.control_plane.provider_admin.rotate'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        body = {**body, 'tenant_id': tenant_id, 'requested_by': body.get('requested_by') or principal.actor_id or principal.subject}
        resource_id = f"provider-admin-rotate:{tenant_id}:{body.get('business_id') or 'unknown'}:{body.get('provider_key') or 'unknown'}"
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=resource_id, body={k: ('***' if k == 'secrets' else v) for k, v in body.items()})
        return provider_admin_handlers.rotate_provider(payload=body)

    @router.post('/control-plane/provider-admin/revoke')
    async def control_plane_provider_revoke(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        tenant_id = tenant_guard.enforce(principal=principal, request_context=request_context, body=body)
        action_name = 'api.control_plane.provider_admin.revoke'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        body = {**body, 'tenant_id': tenant_id, 'requested_by': body.get('requested_by') or principal.actor_id or principal.subject}
        resource_id = f"provider-admin-revoke:{tenant_id}:{body.get('business_id') or 'unknown'}:{body.get('provider_key') or 'unknown'}"
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=resource_id, body=body)
        return provider_admin_handlers.revoke_provider(tenant_id=tenant_id, business_id=str(body.get('business_id') or ''), provider_key=str(body.get('provider_key') or ''), requested_by=str(body.get('requested_by') or 'admin_console'))

    @router.post('/control-plane/provider-admin/reconnect')
    async def control_plane_provider_reconnect(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        tenant_id = tenant_guard.enforce(principal=principal, request_context=request_context, body=body)
        action_name = 'api.control_plane.provider_admin.reconnect'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        body = {**body, 'tenant_id': tenant_id, 'requested_by': body.get('requested_by') or principal.actor_id or principal.subject}
        resource_id = f"provider-admin-reconnect:{tenant_id}:{body.get('business_id') or 'unknown'}:{body.get('provider_key') or 'unknown'}"
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=resource_id, body=body)
        return provider_admin_handlers.reconnect_provider(tenant_id=tenant_id, business_id=str(body.get('business_id') or ''), provider_key=str(body.get('provider_key') or ''), requested_by=str(body.get('requested_by') or 'admin_console'), probe_mode=str(body.get('probe_mode') or 'dry_run'), activate_runtime=bool(body.get('activate_runtime', False)))

    @router.post('/control-plane/provider-runtime/sync')
    async def control_plane_provider_runtime_sync(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        tenant_id = tenant_guard.enforce(principal=principal, request_context=request_context, body=body)
        action_name = 'api.control_plane.provider_runtime.sync'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        body = {**body, 'tenant_id': tenant_id}
        resource_id = f"provider-runtime-sync:{tenant_id}:{body.get('business_id') or 'unknown'}:{body.get('provider_key') or 'unknown'}:{body.get('operation') or 'unknown'}"
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=resource_id, body=body)
        return provider_admin_handlers.trigger_provider_sync(payload=body)

    @router.post('/control-plane/provider-runtime/webhook-ingest')
    async def control_plane_provider_runtime_webhook_ingest(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        tenant_id = tenant_guard.enforce(principal=principal, request_context=request_context, body=body)
        action_name = 'api.control_plane.provider_runtime.webhook_ingest'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        body = {**body, 'tenant_id': tenant_id}
        resource_id = f"provider-runtime-webhook:{tenant_id}:{body.get('business_id') or 'unknown'}:{body.get('provider_key') or 'unknown'}:{body.get('event_key') or 'unknown'}"
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=resource_id, body={**body, 'body': '***'})
        return provider_admin_handlers.ingest_provider_webhook(payload=body)

    @router.post('/control-plane/connectors/{connector_id}/secret-scope/dry-run')
    async def control_plane_connector_secret_scope_dry_run(connector_id: str, request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        tenant_id = tenant_guard.enforce(principal=principal, request_context=request_context, body=body)
        action_name = 'api.control_plane.connectors.secret_scope_dry_run'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'connector-secret-scope:{tenant_id}:{connector_id}:{body.get("secret_name") or "unknown"}', body={**body, 'connector_id': connector_id}, connector_id=connector_id)
        return connector_admin_handlers.dry_run_secret_access(tenant_id=tenant_id, connector_id=connector_id, secret_name=str(body.get('secret_name') or ''), mode=str(body.get('mode') or 'read'), secret_kind=str(body.get('secret_kind') or '') or None)

    @router.get('/control-plane/queue/{tenant_id}/{queue_name}')
    async def control_plane_queue_ops_view(tenant_id: str, queue_name: str, request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.queue.view'
        RoutePermissionGuard(permission=Permission.VIEW_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'queue-ops:{tenant_id}:{queue_name}', queue_name=queue_name)
        return queue_ops_handlers.get_queue_ops_view(tenant_id=tenant_id, queue_name=queue_name)

    @router.get('/control-plane/queue/{tenant_id}/{queue_name}/remediation-analytics')
    async def control_plane_queue_remediation_analytics(tenant_id: str, queue_name: str, request: Request, limit: int = 200) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.queue.remediation_analytics'
        RoutePermissionGuard(permission=Permission.VIEW_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'queue-remediation-analytics:{tenant_id}:{queue_name}', queue_name=queue_name, limit=limit)
        return queue_ops_handlers.get_remediation_analytics(tenant_id=tenant_id, queue_name=queue_name, limit=limit)

    @router.get('/control-plane/queue/{tenant_id}/{queue_name}/remediation-audit')
    async def control_plane_queue_remediation_audit(tenant_id: str, queue_name: str, request: Request, limit: int = 50) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.queue.remediation_audit'
        RoutePermissionGuard(permission=Permission.VIEW_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'queue-remediation-audit:{tenant_id}:{queue_name}', queue_name=queue_name, limit=limit)
        return queue_ops_handlers.list_remediation_audit(tenant_id=tenant_id, queue_name=queue_name, limit=limit)

    @router.post('/control-plane/queue/{tenant_id}/{queue_name}/remediation/{hook_code}')
    async def control_plane_execute_queue_remediation(tenant_id: str, queue_name: str, hook_code: str, request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.queue.remediation_execute'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'queue-remediation:{tenant_id}:{queue_name}:{hook_code}', queue_name=queue_name, hook_code=hook_code)
        return queue_ops_handlers.execute_remediation_hook(tenant_id=tenant_id, queue_name=queue_name, hook_code=hook_code)

    @router.post('/control-plane/webhooks/{connector_id}')
    async def control_plane_receive_webhook(connector_id: str, request: Request) -> dict[str, Any]:
        request_context = RequestContext.from_http_request(request)
        tenant_id = request_context.validated_tenant_id(required=False)
        body = await request.body()
        payload = webhook_handlers.receive(headers={str(k): str(v) for k, v in request.headers.items()}, body=body, tenant_id=tenant_id, connector_id=connector_id, request_context=request_context)
        if not payload['accepted']:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=payload)
        return payload


    if analytics_ops_handlers is not None:
        register_analytics_ops_routes(router=router, analytics_ops_handlers=analytics_ops_handlers, auth_bundle=auth_bundle, authz_bundle=authz_bundle, tenant_guard=tenant_guard, rate_limit_bundle=rate_limit_bundle, security_guard=security_guard)
    if analytics_signed_export_handlers is not None:
        register_analytics_signed_export_routes(router=router, analytics_signed_export_handlers=analytics_signed_export_handlers, auth_bundle=auth_bundle, authz_bundle=authz_bundle, tenant_guard=tenant_guard, rate_limit_bundle=rate_limit_bundle, security_guard=security_guard)



    @router.get('/control-plane/provider-runtime/sync-history')
    async def control_plane_provider_runtime_sync_history(request: Request, tenant_id: str, business_id: str, provider_key: str, limit: int = 20) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.provider_runtime_sync_history'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'provider-runtime-sync-history:{tenant_id}:{business_id}:{provider_key}', business_id=business_id)
        return provider_admin_handlers.list_provider_sync_history(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, limit=limit)

    @router.get('/control-plane/provider-runtime/response-parser')
    async def control_plane_provider_runtime_response_parser(request: Request, provider_key: str) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        action_name = 'api.control_plane.provider_runtime.response_parser'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=principal.tenant_id, resource_id=f'provider-runtime-response-parser:{provider_key}')
        return provider_admin_handlers.describe_provider_response_parser(provider_key=provider_key)

    @router.get('/control-plane/provider-runtime/live-probe')
    async def control_plane_provider_runtime_live_probe(request: Request, tenant_id: str, business_id: str, provider_key: str, mode: str = 'dry_run') -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.provider_runtime.live_probe'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'provider-runtime-live-probe:{tenant_id}:{business_id}:{provider_key}', business_id=business_id)
        return provider_admin_handlers.probe_provider_live(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, mode=mode)

    @router.post('/control-plane/provider-runtime/paginate')
    async def control_plane_provider_runtime_paginate(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        tenant_id = tenant_guard.enforce(principal=principal, request_context=request_context, body=body)
        business_id = str(body.get('business_id') or '').strip()
        action_name = 'api.control_plane.provider_runtime.paginate'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'provider-runtime-paginate:{tenant_id}:{business_id}:{body.get("provider_key")}', business_id=business_id, body=body)
        return provider_admin_handlers.paginate_provider_sync(payload=body)

    @router.get('/control-plane/provider-runtime/live-client')
    async def control_plane_provider_runtime_live_client(request: Request, provider_key: str) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        action_name = 'api.control_plane.provider_runtime.live_client'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=principal.tenant_id, resource_id=f'provider-runtime-live-client:{provider_key}')
        return provider_admin_handlers.describe_provider_live_client(provider_key=provider_key)

    @router.post('/control-plane/provider-runtime/queue-dispatch')
    async def control_plane_provider_runtime_queue_dispatch(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        tenant_id = tenant_guard.enforce(principal=principal, request_context=request_context, body=body)
        business_id = str(body.get('business_id') or '').strip()
        action_name = 'api.control_plane.provider_runtime.queue_dispatch'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'provider-runtime-queue-dispatch:{tenant_id}:{business_id}:{body.get("provider_key")}', business_id=business_id, body=body)
        return provider_admin_handlers.enqueue_provider_sync(payload=body)

    @router.post('/control-plane/provider-runtime/queue-tick')
    async def control_plane_provider_runtime_queue_tick(request: Request) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        tenant_id = tenant_guard.enforce(principal=principal, request_context=request_context, body=body)
        action_name = 'api.control_plane.provider_runtime.queue_tick'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'provider-runtime-queue-tick:{tenant_id}', body=body)
        return provider_admin_handlers.tick_provider_sync_queue(tenant_id=tenant_id)


    @router.get('/control-plane/provider-runtime/incidents')
    async def control_plane_provider_runtime_incidents(request: Request, tenant_id: str, business_id: str, provider_key: str, limit: int = 50) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.provider_runtime.incidents'
        RoutePermissionGuard(permission=Permission.VIEW_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'provider-runtime-incidents:{tenant_id}:{business_id}:{provider_key}', business_id=business_id)
        return provider_admin_handlers.list_provider_runtime_incidents(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, limit=limit)

    @router.get('/control-plane/provider-runtime/queue-metrics')
    async def control_plane_provider_runtime_queue_metrics(request: Request, tenant_id: str) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.provider_runtime.queue_metrics'
        RoutePermissionGuard(permission=Permission.VIEW_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'provider-runtime-queue-metrics:{tenant_id}')
        return provider_admin_handlers.get_provider_queue_metrics(tenant_id=tenant_id)

    @router.get('/control-plane/provider-runtime/queue-jobs')
    async def control_plane_provider_runtime_queue_jobs(request: Request, tenant_id: str, provider_key: str, business_id: str = '', limit: int = 50) -> dict[str, Any]:
        request_context, principal = authorize_request(request=request, auth_bundle=auth_bundle)
        tenant_guard.enforce(principal=principal, request_context=request_context, tenant_id=tenant_id)
        action_name = 'api.control_plane.provider_runtime.queue_jobs'
        RoutePermissionGuard(permission=Permission.MANAGE_TENANT_POLICY, action_name=action_name).enforce(principal=principal, request_context=request_context, authz=authz_bundle)
        enforce_control_plane_security(principal=principal, request_context=request_context, action_name=action_name, tenant_id=tenant_id, resource_id=f'provider-runtime-queue-jobs:{tenant_id}:{business_id}:{provider_key}', business_id=business_id or None)
        return provider_admin_handlers.list_provider_queue_jobs(tenant_id=tenant_id, business_id=business_id or None, provider_key=provider_key, limit=limit)
