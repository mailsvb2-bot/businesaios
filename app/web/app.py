from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from security.owner_factory import ApiSecurityOwnerBundle


def _default_redactor() -> Any:
    from security.payload_redaction import PayloadRedactor

    return PayloadRedactor()


def _web_components() -> tuple[type[Any], type[Any], type[Any]]:
    from app.web.auth import AuthService
    from app.web.routes import Routes
    from app.web.session import SessionStore

    return AuthService, Routes, SessionStore


@dataclass
class WebApp:
    name: str = "businesaios-web"
    settings: Mapping[str, Any] = field(default_factory=dict)
    redactor: Any = field(default_factory=_default_redactor)
    security_adapter: Any | None = None
    security_owner_bundle: ApiSecurityOwnerBundle | None = None
    runtime_infra: Any = None

    def describe(self) -> dict[str, Any]:
        return {"kind": "web_app", "name": self.name, "settings": dict(self.settings)}

    def build(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        AuthService, Routes, SessionStore = _web_components()
        from security.token_policy import TokenPolicy

        data = dict(payload or {})
        tenant_id = str(data.get('tenant_id') or '').strip() or None
        auth_result = AuthService(token_policy=TokenPolicy()).authenticate(dict(data.get('auth_payload') or {})) if data.get('auth_payload') else {'kind': 'auth_result', 'payload': {'security': {'token': {'allowed': False, 'reason': 'missing_auth'}, 'tenant': {'bound': bool(tenant_id)}}}}
        session_result = SessionStore().build(dict(data.get('session_payload') or {})) if data.get('session_payload') else {'kind': 'session', 'payload': {'security': {'session': {'allowed': False, 'invalidate_session': True, 'reason': 'missing_session'}, 'tenant': {'bound': bool(tenant_id)}}}}
        auth_allowed = bool(((auth_result.get('payload') or {}).get('security') or {}).get('token', {}).get('allowed', False))
        session_allowed = bool(((session_result.get('payload') or {}).get('security') or {}).get('session', {}).get('allowed', False))
        routes_payload = dict(data.get('routes_payload') or {})
        routes_payload.setdefault('tenant_id', tenant_id)
        routes_result = Routes().build_default(tenant_id=tenant_id) if not routes_payload.get('routes') else Routes().build(routes_payload)

        security_surface = self._evaluate_security_surface(tenant_id=tenant_id, data=data)
        if not (auth_allowed and session_allowed and bool(security_surface.get('allowed', False))):
            routes_result = {'kind': 'route_table', 'payload': {'tenant_id': tenant_id, 'routes': (), 'summary': {'count': 0, 'auth_required_count': 0, 'tenant_required_count': 0}}}
        return {
            'kind': 'web_app',
            'payload': {
                'tenant_id': tenant_id,
                'tenant_bound': bool(tenant_id),
                'auth': auth_result,
                'session': session_result,
                'routes': routes_result,
                'security_summary': {
                    'auth_allowed': auth_allowed,
                    'session_allowed': session_allowed,
                    'surface_allowed': bool(security_surface.get('allowed', False)),
                    'surface_reason': security_surface.get('reason'),
                },
                'security_surface': security_surface,
                'ready': bool(auth_allowed and session_allowed and bool(security_surface.get('allowed', False))),
            },
        }

    def _evaluate_security_surface(self, *, tenant_id: str | None, data: Mapping[str, Any]) -> dict[str, Any]:
        if not tenant_id:
            return {'allowed': False, 'reason': 'missing_tenant', 'operator_required': True}
        from governance.rbac_contract import ActorContext, RoleId
        from security.access_policy import SecurityAction

        actor = ActorContext(
            actor_id=str((data.get('auth_payload') or {}).get('subject') or 'web-anonymous'),
            tenant_id=tenant_id,
            role_ids=frozenset({RoleId.OWNER}),
            is_service=False,
        )
        adapter = self._resolved_security_adapter()
        auth_payload = dict(data.get('auth_payload') or {})
        session_payload = dict(data.get('session_payload') or {})
        return adapter.evaluate_surface(
            actor=actor,
            resource_type='web_console',
            resource_id='admin_console',
            action=SecurityAction.READ,
            auth_payload=auth_payload,
            session_payload=session_payload,
            compliance_evidence={
                'encryption_at_rest': True,
                'encryption_in_transit': True,
                'immutable_audit_log': True,
                'rbac_enforced': True,
                'session_policy_enforced': True,
                'token_policy_enforced': True,
                'secret_rotation': True,
                'fraud_monitoring': True,
            },
            fraud_signals={'request_rate': float(data.get('request_rate') or 1.0)},
            transport_encrypted=bool(data.get('transport_encrypted', True)),
            classification_input={
                'asset_id': 'web_console',
                'name': 'web admin console',
                'content_type': 'text/html',
                'tags': ('internal', 'admin'),
                'metadata': {'tenant_id': tenant_id},
                'source_system': 'web',
                'region_hint': 'eu',
            },
            audit_payload={'surface': 'web_app'},
        )

    def _resolved_security_adapter(self) -> Any:
        if self.security_adapter is not None:
            return self.security_adapter
        if self.security_owner_bundle is not None:
            return self.security_owner_bundle.adapter
        runtime_bundle = getattr(self.runtime_infra, 'api_security_owner_bundle', None) if self.runtime_infra is not None else None
        runtime_adapter = getattr(runtime_bundle, 'adapter', None)
        if runtime_adapter is not None:
            return runtime_adapter
        return self._default_security_adapter()

    def _default_security_adapter(self) -> Any:
        from security.owner_factory import build_default_security_adapter

        return build_default_security_adapter(audit_path=self.settings.get('security_audit_path') or 'runtime/data/security/web_security_audit.jsonl')


__all__ = ["WebApp"]
