from __future__ import annotations

"""Canonical control-plane security boundary owner.

This module centralizes security evaluation for privileged API surfaces so route
files do not grow their own security brains.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping

from governance.rbac_contract import RoleId
from entrypoints.api.auth_contract import AuthPrincipal
from entrypoints.api.request_context import RequestContext
from entrypoints.api.security_surface_guard import ApiSecuritySurfaceGuard
from security.access_policy import SecurityAction


CANON_API_CONTROL_PLANE_SECURITY_GUARD = True
CANON_API_FINAL_OWNER = True


@dataclass(frozen=True)
class ControlPlaneSecurityRouteSpec:
    resource_type: str
    action: SecurityAction
    classification_tags: tuple[str, ...] = ()
    requires_secret_handling: bool = False
    requires_export_posture: bool = False
    surface: str = 'api_control_plane'


@dataclass(frozen=True)
class ControlPlaneSecurityGuard:
    security_guard: ApiSecuritySurfaceGuard = field(default_factory=ApiSecuritySurfaceGuard.default)

    def enforce(
        self,
        *,
        principal: AuthPrincipal,
        request_context: RequestContext,
        action_name: str,
        tenant_id: str | None,
        resource_id: str,
        body: Mapping[str, Any] | None = None,
        audit_payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        spec = self._spec_for(action_name)
        normalized_tenant = str(tenant_id or principal.tenant_id or request_context.validated_tenant_id(required=False) or 'global').strip()
        classification = self._classification_input(
            principal=principal,
            request_context=request_context,
            tenant_id=normalized_tenant,
            resource_id=resource_id,
            action_name=action_name,
            spec=spec,
            body=body,
        )
        compliance_evidence = self._compliance_evidence(request_context=request_context, spec=spec)
        fraud_signals = self._fraud_signals(request_context=request_context, body=body, spec=spec)
        return self.security_guard.enforce(
            principal=principal,
            request_context=request_context,
            resource_type=spec.resource_type,
            resource_id=resource_id,
            action=spec.action,
            surface=spec.surface,
            classification_input=classification,
            compliance_evidence=compliance_evidence,
            fraud_signals=fraud_signals,
            audit_payload={
                'action_name': action_name,
                'tenant_id': normalized_tenant,
                **dict(audit_payload or {}),
            },
        )

    @staticmethod
    def _spec_for(action_name: str) -> ControlPlaneSecurityRouteSpec:
        name = str(action_name or '').strip()
        exact: dict[str, ControlPlaneSecurityRouteSpec] = {
            'api.control_plane.audit.actions': ControlPlaneSecurityRouteSpec('audit_stream', SecurityAction.READ, ('internal', 'audit', 'control_plane')),
            'api.control_plane.audit.decisions': ControlPlaneSecurityRouteSpec('decision_audit_stream', SecurityAction.READ, ('internal', 'audit', 'decision', 'control_plane')),
            'api.control_plane.approvals.list_open': ControlPlaneSecurityRouteSpec('approval_queue', SecurityAction.READ, ('internal', 'approval', 'control_plane')),
            'api.control_plane.approvals.submit': ControlPlaneSecurityRouteSpec('approval_workflow', SecurityAction.WRITE, ('internal', 'approval', 'write', 'control_plane')),
            'api.control_plane.approvals.decide': ControlPlaneSecurityRouteSpec('approval_workflow', SecurityAction.ADMIN, ('internal', 'approval', 'control_plane', 'privileged')),
            'api.control_plane.admin.list_tenants': ControlPlaneSecurityRouteSpec('tenant_registry', SecurityAction.READ, ('internal', 'tenant', 'control_plane', 'privileged')),
            'api.control_plane.admin.get_tenant_policy': ControlPlaneSecurityRouteSpec('tenant_policy', SecurityAction.ADMIN, ('internal', 'tenant', 'policy', 'control_plane', 'privileged')),
            'api.control_plane.admin.platform_overview': ControlPlaneSecurityRouteSpec('platform_overview', SecurityAction.ADMIN, ('internal', 'platform', 'overview', 'control_plane', 'privileged')),
            'api.control_plane.admin.platform_risks': ControlPlaneSecurityRouteSpec('platform_risks', SecurityAction.ADMIN, ('internal', 'platform', 'risk_registry', 'control_plane', 'privileged')),
            'api.control_plane.admin.platform_dependencies': ControlPlaneSecurityRouteSpec('platform_dependencies', SecurityAction.ADMIN, ('internal', 'platform', 'dependency_graph', 'control_plane', 'privileged')),
            'api.control_plane.admin.platform_remediation': ControlPlaneSecurityRouteSpec('platform_remediation', SecurityAction.ADMIN, ('internal', 'platform', 'remediation', 'control_plane', 'privileged')),
            'api.control_plane.admin.platform_risk_diff': ControlPlaneSecurityRouteSpec('platform_risk_diff', SecurityAction.ADMIN, ('internal', 'platform', 'risk_diff', 'control_plane', 'privileged')),
            'api.control_plane.admin.platform_live_widgets': ControlPlaneSecurityRouteSpec('platform_live_widgets', SecurityAction.ADMIN, ('internal', 'platform', 'live_widgets', 'control_plane', 'privileged')),
            'api.control_plane.admin.platform_visual_conflicts': ControlPlaneSecurityRouteSpec('platform_visual_conflicts', SecurityAction.ADMIN, ('internal', 'platform', 'visual_conflicts', 'control_plane', 'privileged')),
            'api.control_plane.admin.platform_dashboard_layout': ControlPlaneSecurityRouteSpec('platform_dashboard_layout', SecurityAction.ADMIN, ('internal', 'platform', 'dashboard_layout', 'control_plane', 'privileged')),
            'api.control_plane.metrics.global': ControlPlaneSecurityRouteSpec('platform_metrics', SecurityAction.READ, ('internal', 'metrics', 'control_plane')),
            'api.control_plane.metrics.tenant': ControlPlaneSecurityRouteSpec('tenant_metrics', SecurityAction.READ, ('internal', 'metrics', 'tenant', 'control_plane')),
            'api.control_plane.connectors.secret_scope_dry_run': ControlPlaneSecurityRouteSpec('connector_secret_scope', SecurityAction.ADMIN, ('internal', 'connector', 'secret', 'control_plane', 'privileged'), requires_secret_handling=True),
            'api.control_plane.provider_admin.catalog': ControlPlaneSecurityRouteSpec('provider_admin_catalog', SecurityAction.READ, ('internal', 'connector', 'provider', 'control_plane')),
            'api.control_plane.provider_admin.activate': ControlPlaneSecurityRouteSpec('provider_admin_activation', SecurityAction.ADMIN, ('internal', 'connector', 'provider', 'control_plane', 'privileged'), requires_secret_handling=True),
            'api.control_plane.queue.view': ControlPlaneSecurityRouteSpec('queue_ops', SecurityAction.READ, ('internal', 'queue', 'control_plane')),
            'api.control_plane.queue.remediation_analytics': ControlPlaneSecurityRouteSpec('queue_ops_analytics', SecurityAction.READ, ('internal', 'queue', 'analytics', 'control_plane')),
            'api.control_plane.queue.remediation_audit': ControlPlaneSecurityRouteSpec('queue_ops_audit', SecurityAction.READ, ('internal', 'queue', 'audit', 'control_plane')),
            'api.control_plane.queue.remediation_execute': ControlPlaneSecurityRouteSpec('queue_remediation', SecurityAction.ADMIN, ('internal', 'queue', 'remediation', 'control_plane', 'privileged')),
            'api.control_plane.analytics.materialize': ControlPlaneSecurityRouteSpec('analytics_materialization', SecurityAction.ADMIN, ('internal', 'analytics', 'materialize', 'control_plane', 'privileged')),
            'api.control_plane.analytics.enqueue_materialization': ControlPlaneSecurityRouteSpec('analytics_materialization', SecurityAction.ADMIN, ('internal', 'analytics', 'queue', 'control_plane', 'privileged')),
            'api.control_plane.analytics.signed_export': ControlPlaneSecurityRouteSpec('analytics_export', SecurityAction.ADMIN, ('internal', 'analytics', 'export', 'control_plane', 'privileged'), requires_export_posture=True),
        }
        if name in exact:
            return exact[name]
        if name.startswith('api.control_plane.webhooks.'):
            return ControlPlaneSecurityRouteSpec('webhook_ingress', SecurityAction.WRITE, ('connector', 'webhook', 'control_plane'), surface='api_webhook_ingress')
        return ControlPlaneSecurityRouteSpec('control_plane_surface', SecurityAction.READ, ('internal', 'control_plane'))

    @staticmethod
    def _classification_input(
        *,
        principal: AuthPrincipal,
        request_context: RequestContext,
        tenant_id: str,
        resource_id: str,
        action_name: str,
        spec: ControlPlaneSecurityRouteSpec,
        body: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        tags = list(spec.classification_tags)
        payload = dict(body or {})
        if spec.requires_secret_handling:
            tags.extend(['restricted', 'secret'])
        if spec.requires_export_posture:
            tags.append('export')
        if str(payload.get('secret_name') or '').strip():
            tags.extend(['secret_name_present', 'secret'])
        if str(payload.get('connector_id') or '').strip():
            tags.append('connector')
        normalized_tags: list[str] = []
        for item in tags:
            text = str(item).strip().lower()
            if text and text not in normalized_tags:
                normalized_tags.append(text)
        return {
            'asset_id': f'{spec.surface}:{resource_id}',
            'name': action_name,
            'content_type': 'application/json',
            'tags': tuple(normalized_tags),
            'metadata': {
                'tenant_id': tenant_id,
                'subject': principal.subject,
                'actor_id': principal.actor_id or principal.subject,
                'request_id': request_context.normalized_request_id(),
                'path': request_context.metadata.get('path'),
                'method': request_context.metadata.get('method'),
            },
            'source_system': 'api_control_plane',
            'region_hint': str(request_context.metadata.get('region_hint') or 'eu'),
        }

    @staticmethod
    def _compliance_evidence(*, request_context: RequestContext, spec: ControlPlaneSecurityRouteSpec) -> dict[str, object]:
        return {
            'encryption_at_rest': True,
            'encryption_in_transit': bool(request_context.metadata.get('transport_encrypted', True)),
            'immutable_audit_log': True,
            'rbac_enforced': True,
            'session_policy_enforced': True,
            'token_policy_enforced': True,
            'secret_rotation': True,
            'fraud_monitoring': True,
            'secret_scope_enforced': spec.requires_secret_handling,
        }

    @staticmethod
    def _fraud_signals(
        *,
        request_context: RequestContext,
        body: Mapping[str, Any] | None,
        spec: ControlPlaneSecurityRouteSpec,
    ) -> dict[str, float | int | bool]:
        metadata = dict(request_context.metadata)
        payload = dict(body or {})
        return {
            'request_rate': float(metadata.get('request_rate') or 1.0),
            'authentication_failures': float(metadata.get('authentication_failures') or 0.0),
            'geo_velocity': bool(metadata.get('geo_velocity') or False),
            'secret_access_attempt': spec.requires_secret_handling,
            'admin_surface': spec.action is SecurityAction.ADMIN,
            'operator_override': bool(payload.get('operator_override') or False),
            'export_attempt': spec.requires_export_posture,
            'principal_is_service': str(metadata.get('principal_kind') or '').lower() == 'service',
        }


__all__ = [
    'CANON_API_CONTROL_PLANE_SECURITY_GUARD',
    'ControlPlaneSecurityGuard',
    'ControlPlaneSecurityRouteSpec',
]
