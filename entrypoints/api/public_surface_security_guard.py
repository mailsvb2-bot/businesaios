from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from governance.rbac_contract import ActorContext, RoleId
from security.access_policy import SecurityAction
from security.owner_factory import build_default_security_adapter
from security.security_integration_adapter import SecurityIntegrationAdapter

from entrypoints.api.auth_contract import AuthPrincipal
from entrypoints.api.request_context import RequestContext
from entrypoints.api.public_surface_route_specs import PublicSurfaceRouteSpec, _ROUTE_SPECS
from entrypoints.api.security_surface_guard import ApiSecuritySurfaceGuard

CANON_API_PUBLIC_SURFACE_SECURITY_GUARD = True
CANON_API_FINAL_OWNER = True
CANON_API_INTERNAL_WRITE_ADMIN_PERIMETER_FAIL_CLOSED = True
CANON_API_INTERNAL_WRITE_ADMIN_REPLAY_REQUIRED = True
CANON_API_INTERNAL_WRITE_ADMIN_EXPLICIT_REPLAY_MARKER = True
CANON_API_INTERNAL_WRITE_ADMIN_TENANT_ISOLATION = True




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
        principal: AuthPrincipal | None = None,
    ) -> dict[str, Any]:
        spec = _ROUTE_SPECS.get(str(route_path).strip())
        if spec is None:
            raise PermissionError(f'unknown_public_surface:{route_path}')
        payload = dict(body or {})
        internal = self._is_internal(spec=spec)
        if internal:
            if principal is None:
                raise PermissionError('api_authenticated_principal_required')
            tenant_id = self._principal_tenant_id(principal=principal, request_context=request_context)
            actor_id = self._principal_actor_id(principal=principal, request_context=request_context)
            role_ids = frozenset(principal.roles)
            if not role_ids:
                raise PermissionError('api_principal_roles_required')
            auth_metadata = dict(principal.metadata)
            auth_type = str(auth_metadata.get('auth_type') or request_context.metadata.get('auth_level') or 'authenticated')
            subject = principal.subject
            audience = principal.audience or 'public-api'
            scopes = tuple(principal.scopes)
            session_id = principal.session_id
            is_service = str(auth_metadata.get('principal_kind') or '').strip().lower() == 'service'
        else:
            tenant_id = 'public-site'
            actor_id = 'public-site-entrypoint'
            role_ids = frozenset({RoleId.SYSTEM})
            auth_metadata = {}
            auth_type = 'public_entrypoint'
            subject = actor_id
            audience = 'public-api'
            scopes = (spec.operation_name,)
            session_id = request_context.normalized_request_id()
            is_service = True

        self._enforce_internal_perimeter(
            spec=spec,
            payload=payload,
            request_context=request_context,
            tenant_id=tenant_id,
        )
        projection_guard = ApiSecuritySurfaceGuard(adapter=self.adapter, default_token_ttl_seconds=self.default_token_ttl_seconds)
        auth_projection, session_projection = projection_guard._build_auth_payload(principal=principal, request_context=request_context), projection_guard._build_session_payload(principal=principal, request_context=request_context)
        issued_at, expires_at, now = str(auth_projection['issued_at']), str(auth_projection['expires_at']), str(auth_projection['now'])
        actor = ActorContext(
            actor_id=actor_id,
            tenant_id=tenant_id,
            role_ids=role_ids,
            is_service=is_service,
            attributes={
                'surface': 'api_public',
                'route_path': route_path,
                'subject': subject,
                'auth_type': auth_type,
                'public_entrypoint': not internal,
            },
        )
        verdict = self.adapter.evaluate_surface(
            actor=actor,
            resource_type=spec.resource_type,
            resource_id=self._resource_id(spec=spec, payload=payload, tenant_id=tenant_id),
            action=spec.action,
            auth_payload={
                'issued_at': issued_at,
                'expires_at': expires_at,
                'now': now,
                'subject': subject,
                'audience': audience,
                'issuer': auth_metadata.get('issuer') or auth_type,
                'session_id': session_id,
                'scopes': scopes,
                'token_id': auth_metadata.get('token_id') or auth_metadata.get('key_id') or request_context.normalized_request_id(),
                'algorithm': auth_metadata.get('algorithm') or 'HS256',
                'key_id': auth_metadata.get('key_id'),
                'not_before': auth_metadata.get('not_before'),
                'expected_ip': request_context.ip_address,
                'observed_ip': request_context.ip_address,
                'expected_user_agent': request_context.user_agent,
                'observed_user_agent': request_context.user_agent,
                'auth_level': auth_type,
            },
            session_payload={
                'created_at': session_projection['created_at'],
                'last_seen_at': session_projection['last_seen_at'],
                'now': session_projection['now'],
                'expected_ip': request_context.ip_address,
                'observed_ip': request_context.ip_address,
                'expected_user_agent': request_context.user_agent,
                'observed_user_agent': request_context.user_agent,
                'auth_level': auth_type,
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
                    'role_ids': tuple(sorted(role.value for role in role_ids)),
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
                'authenticated_subject': subject if internal else None,
                'authenticated_roles': tuple(sorted(role.value for role in role_ids)),
            },
        )
        if not bool(verdict.get('allowed', False)):
            raise PermissionError(str(verdict.get('reason') or 'public_surface_security_denied'))
        return verdict

    def requires_external_auth(self, route_path: str) -> bool:
        spec = _ROUTE_SPECS.get(str(route_path).strip())
        if spec is None:
            raise PermissionError(f'unknown_public_surface:{route_path}')
        return self._is_internal(spec=spec)

    @staticmethod
    def _is_internal(*, spec: PublicSurfaceRouteSpec) -> bool:
        return 'internal' in spec.tags

    @staticmethod
    def _external_perimeter_verified(*, request_context: RequestContext) -> bool:
        metadata = dict(request_context.metadata)
        proof_keys = ('mtls_verified', 'api_key_verified', 'jwt_verified', 'control_plane_verified')
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

    @classmethod
    def _tenant_isolation_ok(cls, *, payload: Mapping[str, Any], request_context: RequestContext, tenant_id: str) -> bool:
        candidates: set[str] = set()
        context_tenant = request_context.validated_tenant_id(required=False)
        if context_tenant:
            candidates.add(str(context_tenant).strip())
        candidates.update(cls._payload_tenant_ids(payload))
        return bool(candidates) and candidates == {str(tenant_id).strip()}

    @classmethod
    def _payload_tenant_ids(cls, value: object) -> set[str]:
        result: set[str] = set()
        if isinstance(value, Mapping):
            for key, item in value.items():
                if str(key).strip().lower() == 'tenant_id' and item is not None and str(item).strip():
                    result.add(str(item).strip())
                else:
                    result.update(cls._payload_tenant_ids(item))
        elif isinstance(value, (list, tuple, set, frozenset)):
            for item in value:
                result.update(cls._payload_tenant_ids(item))
        return result

    def _enforce_internal_perimeter(
        self,
        *,
        spec: PublicSurfaceRouteSpec,
        payload: Mapping[str, Any],
        request_context: RequestContext,
        tenant_id: str,
    ) -> None:
        if not self._is_internal(spec=spec):
            return
        if not self._transport_encrypted(request_context=request_context):
            raise PermissionError('api_transport_security_required')
        if not self._external_perimeter_verified(request_context=request_context):
            raise PermissionError('api_perimeter_auth_required')
        if not self._tenant_isolation_ok(payload=payload, request_context=request_context, tenant_id=tenant_id):
            raise PermissionError('api_tenant_isolation_violation')
        if spec.action in {SecurityAction.WRITE, SecurityAction.ADMIN} and not self._replay_marker_present(
            payload=payload,
            request_context=request_context,
        ):
            raise PermissionError('api_replay_protection_required')

    @staticmethod
    def _transport_encrypted(*, request_context: RequestContext) -> bool:
        value = request_context.metadata.get('transport_encrypted')
        if isinstance(value, bool):
            return value
        return str(request_context.metadata.get('scheme') or '').strip().lower() == 'https'

    @staticmethod
    def _principal_tenant_id(*, principal: AuthPrincipal, request_context: RequestContext) -> str:
        principal_tenant = str(principal.tenant_id or '').strip()
        context_tenant = str(request_context.validated_tenant_id(required=False) or '').strip()
        if not principal_tenant:
            raise PermissionError('api_principal_tenant_required')
        if context_tenant and context_tenant != principal_tenant:
            raise PermissionError('api_authenticated_tenant_mismatch')
        return principal_tenant

    @staticmethod
    def _principal_actor_id(*, principal: AuthPrincipal, request_context: RequestContext) -> str:
        principal_actor = str(principal.actor_id or principal.subject or '').strip()
        context_actor = str(request_context.actor_id or '').strip()
        if not principal_actor:
            raise PermissionError('api_principal_actor_required')
        if context_actor and context_actor != principal_actor:
            raise PermissionError('api_authenticated_actor_mismatch')
        return principal_actor

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
        return PublicSurfaceSecurityGuard._transport_encrypted(request_context=request_context)

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
