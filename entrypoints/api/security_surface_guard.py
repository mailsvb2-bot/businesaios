from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from governance.rbac_contract import ActorContext
from entrypoints.api.auth_contract import AuthPrincipal
from entrypoints.api.request_context import RequestContext
from security.access_policy import SecurityAction
from security.owner_factory import build_default_security_adapter
from security.security_integration_adapter import SecurityIntegrationAdapter


CANON_API_SECURITY_SURFACE_GUARD = True
CANON_API_FINAL_OWNER = True


@dataclass(frozen=True)
class ApiSecuritySurfaceGuard:
    adapter: SecurityIntegrationAdapter
    default_token_ttl_seconds: int = 300

    @classmethod
    def default(cls) -> 'ApiSecuritySurfaceGuard':
        return cls(adapter=build_default_security_adapter(audit_path='runtime/data/security/api_security_audit.jsonl'))

    def evaluate(
        self,
        *,
        principal: AuthPrincipal,
        request_context: RequestContext,
        resource_type: str,
        resource_id: str,
        action: SecurityAction,
        surface: str,
        compliance_evidence: Mapping[str, object] | None = None,
        fraud_signals: Mapping[str, float | int | bool] | None = None,
        classification_input: Mapping[str, Any] | None = None,
        audit_payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        actor = ActorContext(
            actor_id=principal.actor_id or principal.subject,
            tenant_id=request_context.validated_tenant_id(required=False) or principal.tenant_id or '',
            role_ids=frozenset(principal.roles),
            is_service=str(principal.metadata.get('principal_kind') or '') == 'service',
            attributes={
                'subject': principal.subject,
                'scopes': list(principal.scopes),
                'surface': surface,
            },
        )
        auth_payload = self._build_auth_payload(principal=principal, request_context=request_context)
        session_payload = self._build_session_payload(principal=principal, request_context=request_context)
        evidence = dict(self._default_compliance_evidence(request_context=request_context))
        evidence.update(dict(compliance_evidence or {}))
        signals = dict(self._default_fraud_signals(request_context=request_context))
        signals.update(dict(fraud_signals or {}))
        classification = dict(self._default_classification_input(
            principal=principal,
            request_context=request_context,
            resource_type=resource_type,
            resource_id=resource_id,
            surface=surface,
        ))
        classification.update(dict(classification_input or {}))
        return self.adapter.evaluate_surface(
            actor=actor,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            auth_payload=auth_payload,
            session_payload=session_payload,
            compliance_evidence=evidence,
            fraud_signals=signals,
            transport_encrypted=self._transport_encrypted(request_context=request_context),
            classification_input=classification,
            audit_payload={
                'surface': surface,
                'request_id': request_context.normalized_request_id(),
                'correlation_id': request_context.normalized_correlation_id(),
                **dict(audit_payload or {}),
            },
        )

    def enforce(self, **kwargs: Any) -> dict[str, Any]:
        verdict = self.evaluate(**kwargs)
        if not bool(verdict.get('allowed', False)):
            raise PermissionError(str(verdict.get('reason') or 'security_denied'))
        return verdict

    def _build_auth_payload(self, *, principal: AuthPrincipal, request_context: RequestContext) -> dict[str, Any]:
        metadata = dict(principal.metadata)
        now = _coerce_dt(metadata.get('security_now')) or datetime.now(timezone.utc)
        issued_at = _coerce_dt(metadata.get('issued_at')) or _coerce_dt(metadata.get('created_at')) or (now - timedelta(seconds=60))
        expires_at = _coerce_dt(metadata.get('expires_at')) or (now + timedelta(seconds=int(self.default_token_ttl_seconds)))
        audience = principal.audience or _text(metadata.get('audience')) or 'control-plane'
        issuer = _text(metadata.get('issuer')) or _text(metadata.get('auth_type')) or 'api-security-surface'
        algorithm = _text(metadata.get('algorithm'))
        if algorithm is None and _text(metadata.get('auth_type')) == 'jwt':
            algorithm = 'HS256'
        return {
            'issued_at': issued_at.isoformat(),
            'expires_at': expires_at.isoformat(),
            'now': now.isoformat(),
            'subject': principal.subject,
            'audience': audience,
            'issuer': issuer,
            'session_id': principal.session_id,
            'scopes': list(principal.scopes),
            'token_id': _text(metadata.get('token_id')) or _text(metadata.get('key_id')),
            'key_id': _text(metadata.get('key_id')),
            'algorithm': algorithm,
            'expected_ip': _text(metadata.get('bound_ip')),
            'observed_ip': request_context.ip_address,
            'expected_user_agent': _text(metadata.get('bound_user_agent')),
            'observed_user_agent': request_context.user_agent,
            'auth_level': _text(metadata.get('auth_level')),
        }

    def _build_session_payload(self, *, principal: AuthPrincipal, request_context: RequestContext) -> dict[str, Any]:
        metadata = dict(principal.metadata)
        now = _coerce_dt(metadata.get('security_now')) or datetime.now(timezone.utc)
        created_at = _coerce_dt(metadata.get('session_created_at')) or _coerce_dt(metadata.get('issued_at')) or (now - timedelta(seconds=60))
        last_seen_at = _coerce_dt(metadata.get('last_seen_at')) or now
        return {
            'created_at': created_at.isoformat(),
            'last_seen_at': last_seen_at.isoformat(),
            'now': now.isoformat(),
            'expected_ip': _text(metadata.get('bound_ip')),
            'observed_ip': request_context.ip_address,
            'expected_user_agent': _text(metadata.get('bound_user_agent')),
            'observed_user_agent': request_context.user_agent,
            'auth_level': _text(metadata.get('auth_level')),
            'mfa_verified_at': _coerce_dt(metadata.get('mfa_verified_at')).isoformat() if _coerce_dt(metadata.get('mfa_verified_at')) else None,
        }

    @staticmethod
    def _transport_encrypted(*, request_context: RequestContext) -> bool:
        value = request_context.metadata.get('transport_encrypted')
        if isinstance(value, bool):
            return value
        if value is not None:
            return str(value).strip().lower() in {'1', 'true', 'yes', 'on', 'https'}
        scheme = str(request_context.metadata.get('scheme') or '').strip().lower()
        if scheme:
            return scheme == 'https'
        return False

    @staticmethod
    def _default_compliance_evidence(*, request_context: RequestContext) -> dict[str, object]:
        return {
            'encryption_at_rest': True,
            'encryption_in_transit': ApiSecuritySurfaceGuard._transport_encrypted(request_context=request_context),
            'immutable_audit_log': True,
            'rbac_enforced': True,
            'session_policy_enforced': True,
            'token_policy_enforced': True,
            'secret_rotation': True,
            'fraud_monitoring': True,
        }

    @staticmethod
    def _default_fraud_signals(*, request_context: RequestContext) -> dict[str, float | int | bool]:
        metadata = dict(request_context.metadata)
        return {
            'request_rate': float(metadata.get('request_rate') or 1.0),
            'authentication_failures': float(metadata.get('authentication_failures') or 0.0),
            'geo_velocity': bool(metadata.get('geo_velocity') or False),
        }

    @staticmethod
    def _default_classification_input(
        *,
        principal: AuthPrincipal,
        request_context: RequestContext,
        resource_type: str,
        resource_id: str,
        surface: str,
    ) -> dict[str, Any]:
        auth_type = str(principal.metadata.get('auth_type') or 'api')
        return {
            'asset_id': f'{surface}:{resource_id}',
            'name': f'{surface} {resource_type}',
            'content_type': 'application/json',
            'tags': (
                'internal',
                'token',
                auth_type,
                surface,
                'control_plane',
            ),
            'metadata': {
                'tenant_id': request_context.validated_tenant_id(required=False) or principal.tenant_id,
                'actor_id': principal.actor_id or principal.subject,
                'resource_type': resource_type,
            },
            'source_system': 'api',
            'region_hint': str(request_context.metadata.get('region_hint') or 'eu'),
        }


def _text(value: object) -> str | None:
    text = str(value or '').strip()
    return text or None


def _coerce_dt(value: object) -> datetime | None:
    text = _text(value)
    if text is None:
        return None
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


__all__ = [
    'ApiSecuritySurfaceGuard',
    'CANON_API_FINAL_OWNER',
    'CANON_API_SECURITY_SURFACE_GUARD',
]
