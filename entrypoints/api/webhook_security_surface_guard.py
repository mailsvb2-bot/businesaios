from __future__ import annotations

"""Canonical security owner for verified webhook ingress.

Webhook signature verification proves origin. This guard turns that result into
canonical security evidence without introducing a second business decision path.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from governance.rbac_contract import RoleId
from entrypoints.api.auth_contract import AuthPrincipal
from entrypoints.api.request_context import RequestContext
from security.access_policy import SecurityAction
from security.owner_factory import build_default_security_adapter
from security.security_integration_adapter import SecurityIntegrationAdapter
from security.webhook_signature_verifier import WebhookVerificationResult


CANON_API_WEBHOOK_SECURITY_SURFACE_GUARD = True
CANON_API_FINAL_OWNER = True


@dataclass(frozen=True)
class WebhookSecuritySurfaceGuard:
    adapter: SecurityIntegrationAdapter

    @classmethod
    def default(cls) -> 'WebhookSecuritySurfaceGuard':
        return cls(adapter=build_default_security_adapter(audit_path='runtime/data/security/webhook_security_audit.jsonl'))

    def enforce(
        self,
        *,
        verification: WebhookVerificationResult,
        request_context: RequestContext,
        tenant_id: str | None,
        connector_id: str | None,
        body: bytes,
        headers: Mapping[str, str],
    ) -> dict[str, Any]:
        if not verification.verified:
            raise PermissionError(str(verification.reason or 'webhook_not_verified'))
        now = datetime.now(timezone.utc)
        principal = AuthPrincipal(
            subject=f'webhook:{str(connector_id or "unknown").strip() or "unknown"}',
            tenant_id=str(tenant_id or 'global').strip() or 'global',
            actor_id=f'webhook:{str(connector_id or "unknown").strip() or "unknown"}',
            roles=(RoleId.SYSTEM,),
            scopes=('webhook:ingest',),
            audience='control-plane-webhook',
            metadata={
                'auth_type': 'webhook_signature',
                'principal_kind': 'service',
                'issuer': 'webhook-signature-verifier',
                'algorithm': 'HS256',
                'key_id': verification.key_id,
                'issued_at': now.isoformat(),
                'expires_at': (now + timedelta(seconds=60)).isoformat(),
                'session_created_at': now.isoformat(),
                'last_seen_at': now.isoformat(),
            },
        )
        actor_tenant = principal.tenant_id or 'global'

        verdict = self.adapter.evaluate_surface(
            actor=self._actor_from_principal(principal),
            resource_type='webhook_ingress',
            resource_id=f'{actor_tenant}:{str(connector_id or "unknown").strip() or "unknown"}',
            action=SecurityAction.WRITE,
            auth_payload={
                'issued_at': principal.metadata['issued_at'],
                'expires_at': principal.metadata['expires_at'],
                'now': now.isoformat(),
                'subject': principal.subject,
                'audience': principal.audience,
                'issuer': principal.metadata['issuer'],
                'scopes': principal.scopes,
                'key_id': verification.key_id,
                'token_id': verification.key_id,
                'algorithm': principal.metadata['algorithm'],
                'expected_ip': None,
                'observed_ip': request_context.ip_address,
                'expected_user_agent': None,
                'observed_user_agent': request_context.user_agent,
                'auth_level': 'signed_webhook',
            },
            session_payload={
                'created_at': principal.metadata['session_created_at'],
                'last_seen_at': principal.metadata['last_seen_at'],
                'now': now.isoformat(),
                'expected_ip': None,
                'observed_ip': request_context.ip_address,
                'expected_user_agent': None,
                'observed_user_agent': request_context.user_agent,
                'auth_level': 'signed_webhook',
            },
            compliance_evidence={
                'encryption_at_rest': True,
                'encryption_in_transit': bool(request_context.metadata.get('transport_encrypted', True)),
                'immutable_audit_log': True,
                'rbac_enforced': True,
                'session_policy_enforced': True,
                'token_policy_enforced': True,
                'secret_rotation': True,
                'fraud_monitoring': True,
                'webhook_signature_verified': True,
            },
            fraud_signals={
                'request_rate': float(request_context.metadata.get('request_rate') or 1.0),
                'authentication_failures': 0.0,
                'geo_velocity': bool(request_context.metadata.get('geo_velocity') or False),
                'connector_context_missing': not bool(str(connector_id or '').strip()),
                'tenant_context_missing': not bool(str(tenant_id or '').strip()),
            },
            transport_encrypted=bool(request_context.metadata.get('transport_encrypted', True)),
            classification_input={
                'asset_id': f'webhook:{actor_tenant}:{str(connector_id or "unknown").strip() or "unknown"}',
                'name': 'control-plane webhook ingress',
                'content_type': str(_header(headers, 'content-type') or 'application/octet-stream'),
                'tags': ('connector', 'webhook', 'internal_write', 'control_plane', 'token'),
                'metadata': {
                    'tenant_id': actor_tenant,
                    'connector_id': connector_id,
                    'content_digest': verification.content_digest,
                    'body_size': len(body),
                },
                'source_system': 'api_webhook',
                'region_hint': str(request_context.metadata.get('region_hint') or 'eu'),
            },
            audit_payload={
                'surface': 'api_webhook_ingress',
                'connector_id': connector_id,
                'request_id': request_context.normalized_request_id(),
                'correlation_id': request_context.normalized_correlation_id(),
                'verification_reason': verification.reason,
                'content_digest': verification.content_digest,
            },
        )
        if not bool(verdict.get('allowed', False)):
            raise PermissionError(str(verdict.get('reason') or 'webhook_security_denied'))
        return verdict


    @staticmethod
    def _actor_from_principal(principal: AuthPrincipal):
        from governance.rbac_contract import ActorContext

        return ActorContext(
            actor_id=principal.actor_id or principal.subject,
            tenant_id=principal.tenant_id or 'global',
            role_ids=frozenset(principal.roles),
            is_service=True,
            attributes={
                'subject': principal.subject,
                'surface': 'api_webhook_ingress',
                'scopes': list(principal.scopes),
            },
        )


def _header(headers: Mapping[str, str], name: str) -> str | None:
    target = str(name).lower()
    for key, value in headers.items():
        if str(key).lower() == target:
            text = str(value).strip()
            return text or None
    return None


__all__ = [
    'CANON_API_WEBHOOK_SECURITY_SURFACE_GUARD',
    'WebhookSecuritySurfaceGuard',
]
