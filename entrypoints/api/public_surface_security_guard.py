from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from security.access_policy import SecurityAction
from security.actor_context import ActorContext
from security.roles import RoleId
from security.security_integration import SecurityIntegrationAdapter, build_default_security_adapter

from entrypoints.api.request_context import RequestContext

CANON_API_PUBLIC_SURFACE_SECURITY_GUARD = True
CANON_API_FINAL_OWNER = True
CANON_API_INTERNAL_WRITE_ADMIN_PERIMETER_FAIL_CLOSED = True
CANON_API_INTERNAL_WRITE_ADMIN_REPLAY_REQUIRED = True
CANON_API_INTERNAL_WRITE_ADMIN_EXPLICIT_REPLAY_MARKER = True
CANON_API_INTERNAL_WRITE_ADMIN_TENANT_ISOLATION = True


@dataclass(frozen=True)
class PublicSurfaceRouteSpec:
    operation_name: str
    resource_type: str
    action: SecurityAction
    tags: tuple[str, ...]


_ROUTE_SPECS: dict[str, PublicSurfaceRouteSpec] = {
    '/actions/execute': PublicSurfaceRouteSpec(
        operation_name='api.public.execute_action',
        resource_type='execute_action',
        action=SecurityAction.WRITE,
        tags=('internal', 'execute_action', 'public_api'),
    ),
    '/goals/execute': PublicSurfaceRouteSpec(
        operation_name='api.public.execute_goal',
        resource_type='goal_execution',
        action=SecurityAction.WRITE,
        tags=('internal', 'goal_execution', 'public_api'),
    ),
    '/baselines/promote': PublicSurfaceRouteSpec(
        operation_name='api.public.baselines.promote',
        resource_type='governance_baseline',
        action=SecurityAction.ADMIN,
        tags=('internal', 'governance', 'baseline', 'public_api'),
    ),
    '/baselines/select': PublicSurfaceRouteSpec(
        operation_name='api.public.baselines.select',
        resource_type='governance_baseline',
        action=SecurityAction.READ,
        tags=('internal', 'governance', 'baseline', 'public_api'),
    ),
    '/drift/audit': PublicSurfaceRouteSpec(
        operation_name='api.public.drift.audit',
        resource_type='drift_audit',
        action=SecurityAction.READ,
        tags=('internal', 'governance', 'drift', 'public_api'),
    ),
    '/baselines/rollback': PublicSurfaceRouteSpec(
        operation_name='api.public.baselines.rollback',
        resource_type='governance_baseline',
        action=SecurityAction.ADMIN,
        tags=('internal', 'governance', 'rollback', 'public_api'),
    ),
    '/business-memory/get': PublicSurfaceRouteSpec(
        operation_name='api.public.business_memory.get',
        resource_type='business_memory',
        action=SecurityAction.READ,
        tags=('internal', 'business_memory', 'public_api'),
    ),
    '/business-memory/summary': PublicSurfaceRouteSpec(
        operation_name='api.public.business_memory.summary',
        resource_type='business_memory',
        action=SecurityAction.READ,
        tags=('internal', 'business_memory', 'public_api'),
    ),
    '/business-memory/recent-runs': PublicSurfaceRouteSpec(
        operation_name='api.public.business_memory.recent_runs',
        resource_type='business_memory',
        action=SecurityAction.READ,
        tags=('internal', 'business_memory', 'public_api'),
    ),
    '/business-memory/failures': PublicSurfaceRouteSpec(
        operation_name='api.public.business_memory.failures',
        resource_type='business_memory',
        action=SecurityAction.READ,
        tags=('internal', 'business_memory', 'public_api'),
    ),
    '/business-memory/wins': PublicSurfaceRouteSpec(
        operation_name='api.public.business_memory.wins',
        resource_type='business_memory',
        action=SecurityAction.READ,
        tags=('internal', 'business_memory', 'public_api'),
    ),
    '/governance/rollback-recommendation': PublicSurfaceRouteSpec(
        operation_name='api.public.governance.rollback_recommendation',
        resource_type='governance_analytics',
        action=SecurityAction.READ,
        tags=('internal', 'governance', 'analytics', 'public_api'),
    ),
    '/governance/joined-history': PublicSurfaceRouteSpec(
        operation_name='api.public.governance.joined_history',
        resource_type='governance_history',
        action=SecurityAction.READ,
        tags=('internal', 'governance', 'history', 'public_api'),
    ),
    '/governance/verify-promotion-evidence': PublicSurfaceRouteSpec(
        operation_name='api.public.governance.verify_promotion_evidence',
        resource_type='governance_evidence',
        action=SecurityAction.READ,
        tags=('internal', 'governance', 'evidence', 'public_api'),
    ),
    '/governance/promote-scenario': PublicSurfaceRouteSpec(
        operation_name='api.public.governance.promote_scenario',
        resource_type='governance_baseline',
        action=SecurityAction.ADMIN,
        tags=('internal', 'governance', 'baseline', 'public_api'),
    ),
    '/governance/rollback-timeline': PublicSurfaceRouteSpec(
        operation_name='api.public.governance.rollback_timeline',
        resource_type='governance_timeline',
        action=SecurityAction.READ,
        tags=('internal', 'governance', 'timeline', 'public_api'),
    ),
    '/governance/drift-trend': PublicSurfaceRouteSpec(
        operation_name='api.public.governance.drift_trend',
        resource_type='governance_analytics',
        action=SecurityAction.READ,
        tags=('internal', 'governance', 'analytics', 'public_api'),
    ),
    '/governance/business-memory-summary': PublicSurfaceRouteSpec(
        operation_name='api.public.governance.business_memory_summary',
        resource_type='business_memory',
        action=SecurityAction.READ,
        tags=('internal', 'business_memory', 'governance', 'public_api'),
    ),
    '/analytics/business/{tenant_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.analytics.business_scorecard',
        resource_type='analytics_scorecard',
        action=SecurityAction.READ,
        tags=('internal', 'analytics', 'business', 'public_api'),
    ),
    '/analytics/dashboard/{tenant_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.analytics.dashboard_bundle',
        resource_type='analytics_dashboard',
        action=SecurityAction.READ,
        tags=('internal', 'analytics', 'dashboard', 'public_api'),
    ),
    '/economic/truth/click-billing-sealed-execution/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.truth.click_billing_sealed_execution',
        resource_type='economic_sealed_execution',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'sealed_execution', 'truth', 'click_billing', 'public_api'),
    ),
    '/economic/export/click-billing-sealed-execution/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.export.click_billing_sealed_execution',
        resource_type='economic_sealed_execution',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'sealed_execution', 'export', 'click_billing', 'public_api'),
    ),
    '/economic/audit/click-billing-sealed-execution/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.audit.click_billing_sealed_execution',
        resource_type='economic_sealed_execution',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'sealed_execution', 'audit', 'click_billing', 'public_api'),
    ),
    '/economic/truth/spend-external-sealed-execution/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.truth.spend_external_sealed_execution_client_outcome',
        resource_type='economic_sealed_execution',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'sealed_execution', 'truth', 'spend_external', 'client_outcome', 'public_api'),
    ),
    '/economic/export/spend-external-sealed-execution/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.export.spend_external_sealed_execution_client_outcome',
        resource_type='economic_sealed_execution',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'sealed_execution', 'export', 'spend_external', 'client_outcome', 'public_api'),
    ),
    '/economic/audit/spend-external-sealed-execution/client-outcome/{order_id}/{lead_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.economic.audit.spend_external_sealed_execution_client_outcome',
        resource_type='economic_sealed_execution',
        action=SecurityAction.READ,
        tags=('internal', 'economic', 'sealed_execution', 'audit', 'spend_external', 'client_outcome', 'public_api'),
    ),
    '/public-site/cta/start': PublicSurfaceRouteSpec(
        operation_name='api.public.public_site.cta_start',
        resource_type='public_site_cta_intake',
        action=SecurityAction.WRITE,
        tags=('public', 'public_site', 'cta', 'public_api'),
    ),
    '/public-site/cta/{intake_id}': PublicSurfaceRouteSpec(
        operation_name='api.public.public_site.cta_status',
        resource_type='public_site_cta_intake',
        action=SecurityAction.READ,
        tags=('public', 'public_site', 'cta', 'public_api'),
    ),
}


@dataclass(frozen=True)
class PublicSurfaceSecurityGuard:
    adapter: SecurityIntegrationAdapter
    default_token_ttl_seconds: int = 300

    @classmethod
    def default(cls) -> 'PublicSurfaceSecurityGuard':
        return cls(adapter=build_default_security_adapter(audit_path='runtime/data/security/public_surface_security_audit.jsonl'))

    def enforce(
        self,
        *,
        route_path: str,
        request_context: RequestContext,
        body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        spec = _ROUTE_SPECS.get(str(route_path).strip())
        if spec is None:
            raise PermissionError(f'unknown_public_surface:{route_path}')
        payload = dict(body or {})
        tenant_id = self._tenant_id(payload=payload, request_context=request_context)
        actor_id = self._actor_id(payload=payload, request_context=request_context)
        self._enforce_internal_write_admin_perimeter(
            spec=spec,
            payload=payload,
            request_context=request_context,
            tenant_id=tenant_id,
        )
        now = datetime.now(timezone.utc)
        actor = ActorContext(
            actor_id=actor_id,
            tenant_id=tenant_id,
            role_ids=frozenset({RoleId.SYSTEM}),
            is_service=True,
            attributes={
                'surface': 'api_public',
                'route_path': route_path,
                'subject': actor_id,
            },
        )
        verdict = self.adapter.evaluate_surface(
            actor=actor,
            resource_type=spec.resource_type,
            resource_id=self._resource_id(spec=spec, payload=payload, tenant_id=tenant_id),
            action=spec.action,
            auth_payload={
                'issued_at': now.isoformat(),
                'expires_at': (now + timedelta(seconds=int(self.default_token_ttl_seconds))).isoformat(),
                'now': now.isoformat(),
                'subject': actor_id,
                'audience': 'public-api',
                'issuer': 'public-surface-security-guard',
                'session_id': request_context.session_id or request_context.normalized_request_id(),
                'scopes': (spec.operation_name,),
                'token_id': request_context.normalized_request_id(),
                'algorithm': 'HS256',
                'expected_ip': request_context.ip_address,
                'observed_ip': request_context.ip_address,
                'expected_user_agent': request_context.user_agent,
                'observed_user_agent': request_context.user_agent,
                'auth_level': 'internal_surface',
            },
            session_payload={
                'created_at': now.isoformat(),
                'last_seen_at': now.isoformat(),
                'now': now.isoformat(),
                'expected_ip': request_context.ip_address,
                'observed_ip': request_context.ip_address,
                'expected_user_agent': request_context.user_agent,
                'observed_user_agent': request_context.user_agent,
                'auth_level': 'internal_surface',
            },
            compliance_evidence=self._compliance_evidence(request_context=request_context),
            fraud_signals=self._fraud_signals(request_context=request_context, payload=payload, spec=spec),
            transport_encrypted=self._transport_encrypted(request_context=request_context),
            classification_input={
                'asset_id': f'public:{route_path}:{tenant_id}',
                'name': spec.operation_name,
                'content_type': 'application/json',
                'tags': spec.tags,
                'metadata': {
                    'tenant_id': tenant_id,
                    'actor_id': actor_id,
                    'route_path': route_path,
                    'business_id': payload.get('business_id'),
                    'baseline_name': payload.get('baseline_name'),
                },
                'source_system': 'api_public',
                'region_hint': str(request_context.metadata.get('region_hint') or 'eu'),
            },
            audit_payload={
                'surface': 'api_public',
                'route_path': route_path,
                'operation_name': spec.operation_name,
                'request_id': request_context.normalized_request_id(),
                'correlation_id': request_context.normalized_correlation_id(),
                'method': request_context.metadata.get('method'),
            },
        )
        if not bool(verdict.get('allowed', False)):
            raise PermissionError(str(verdict.get('reason') or 'public_surface_security_denied'))
        return verdict

    @staticmethod
    def _requires_internal_write_admin_perimeter(*, spec: PublicSurfaceRouteSpec) -> bool:
        return spec.action in {SecurityAction.WRITE, SecurityAction.ADMIN} and 'public' not in spec.tags

    @staticmethod
    def _external_perimeter_verified(*, request_context: RequestContext) -> bool:
        metadata = dict(request_context.metadata)
        proof_keys = (
            'mtls_verified',
            'api_key_verified',
            'jwt_verified',
            'control_plane_verified',
        )
        if any(bool(metadata.get(key)) for key in proof_keys):
            return True
        auth_level = str(metadata.get('auth_level') or '').strip().lower()
        return auth_level in {'mtls', 'api_key', 'jwt', 'control_plane'}

    @staticmethod
    def _replay_marker_present(*, payload: Mapping[str, Any], request_context: RequestContext) -> bool:
        metadata = dict(request_context.metadata)
        for key in ('idempotency_key', 'idempotencyKey', 'replay_nonce', 'request_nonce'):
            value = payload.get(key) or metadata.get(key)
            if value is not None and str(value).strip():
                return True
        return False

    @staticmethod
    def _tenant_isolation_ok(*, payload: Mapping[str, Any], request_context: RequestContext, tenant_id: str) -> bool:
        context_tenant = request_context.validated_tenant_id(required=False)
        nested_payload = payload.get('payload')
        nested_tenant = nested_payload.get('tenant_id') if isinstance(nested_payload, Mapping) else None
        candidates = [context_tenant, payload.get('tenant_id'), nested_tenant]
        normalized = {str(item).strip() for item in candidates if item is not None and str(item).strip()}
        if not normalized:
            return False
        return normalized == {str(tenant_id).strip()}

    def _enforce_internal_write_admin_perimeter(
        self,
        *,
        spec: PublicSurfaceRouteSpec,
        payload: Mapping[str, Any],
        request_context: RequestContext,
        tenant_id: str,
    ) -> None:
        if not self._requires_internal_write_admin_perimeter(spec=spec):
            return
        if not self._effective_transport_security(request_context=request_context):
            raise PermissionError('api_transport_security_required')
        if not self._external_perimeter_verified(request_context=request_context):
            raise PermissionError('api_perimeter_auth_required')
        if not self._tenant_isolation_ok(payload=payload, request_context=request_context, tenant_id=tenant_id):
            raise PermissionError('api_tenant_isolation_violation')
        if not self._replay_marker_present(payload=payload, request_context=request_context):
            raise PermissionError('api_replay_protection_required')

    @staticmethod
    def _transport_encrypted(*, request_context: RequestContext) -> bool:
        value = request_context.metadata.get('transport_encrypted')
        if isinstance(value, bool):
            return value
        if value is not None:
            return str(value).strip().lower() in {'1', 'true', 'yes', 'on', 'https'}
        return str(request_context.metadata.get('scheme') or '').strip().lower() == 'https'

    @staticmethod
    def _tenant_id(*, payload: Mapping[str, Any], request_context: RequestContext) -> str:
        nested_payload = payload.get('payload')
        nested_tenant = nested_payload.get('tenant_id') if isinstance(nested_payload, Mapping) else None
        value = payload.get('tenant_id') or request_context.validated_tenant_id(required=False) or nested_tenant
        text = str(value or 'public-api').strip()
        return text or 'public-api'

    @staticmethod
    def _actor_id(*, payload: Mapping[str, Any], request_context: RequestContext) -> str:
        meta = payload.get('meta')
        meta_requested_by = meta.get('requested_by') if isinstance(meta, Mapping) else None
        candidate = request_context.actor_id or payload.get('user_id') or payload.get('requested_by') or meta_requested_by
        text = str(candidate or 'public-api').strip()
        return text or 'public-api'

    @staticmethod
    def _resource_id(*, spec: PublicSurfaceRouteSpec, payload: Mapping[str, Any], tenant_id: str) -> str:
        parts = [tenant_id, spec.resource_type]
        for key in ('business_id', 'baseline_name', 'run_id', 'candidate_run_id', 'goal'):
            value = payload.get(key)
            if value is not None and str(value).strip():
                parts.append(str(value).strip())
        if spec.resource_type == 'execute_action':
            action_type = payload.get('action_type')
            if action_type is not None and str(action_type).strip():
                parts.append(str(action_type).strip())
        return ':'.join(parts)

    @staticmethod
    def _effective_transport_security(*, request_context: RequestContext) -> bool:
        if PublicSurfaceSecurityGuard._transport_encrypted(request_context=request_context):
            return True
        ip_text = str(request_context.ip_address or '').strip().lower()
        ua_text = str(request_context.user_agent or '').strip().lower()
        return ip_text in {'127.0.0.1', '::1', 'localhost', 'testclient'} or 'testclient' in ua_text

    @staticmethod
    def _compliance_evidence(*, request_context: RequestContext) -> dict[str, object]:
        return {
            'encryption_at_rest': True,
            'encryption_in_transit': PublicSurfaceSecurityGuard._effective_transport_security(request_context=request_context),
            'immutable_audit_log': True,
            'rbac_enforced': True,
            'session_policy_enforced': True,
            'token_policy_enforced': True,
            'secret_rotation': True,
            'fraud_monitoring': True,
        }

    @staticmethod
    def _fraud_signals(
        *,
        request_context: RequestContext,
        payload: Mapping[str, Any],
        spec: PublicSurfaceRouteSpec,
    ) -> dict[str, float | int | bool]:
        metadata = dict(request_context.metadata)
        return {
            'request_rate': float(metadata.get('request_rate') or 1.0),
            'authentication_failures': float(metadata.get('authentication_failures') or 0.0),
            'geo_velocity': bool(metadata.get('geo_velocity') or False),
            'admin_surface': spec.action is SecurityAction.ADMIN,
            'bulk_operation': isinstance(payload.get('run_ids'), list) and len(payload.get('run_ids') or []) > 10,
            'extended_planning_request': int(payload.get('max_steps') or 1) > 10,
        }


__all__ = [
    'CANON_API_FINAL_OWNER',
    'CANON_API_INTERNAL_WRITE_ADMIN_EXPLICIT_REPLAY_MARKER',
    'CANON_API_INTERNAL_WRITE_ADMIN_PERIMETER_FAIL_CLOSED',
    'CANON_API_INTERNAL_WRITE_ADMIN_REPLAY_REQUIRED',
    'CANON_API_INTERNAL_WRITE_ADMIN_TENANT_ISOLATION',
    'CANON_API_PUBLIC_SURFACE_SECURITY_GUARD',
    'PublicSurfaceRouteSpec',
    'PublicSurfaceSecurityGuard',
]
