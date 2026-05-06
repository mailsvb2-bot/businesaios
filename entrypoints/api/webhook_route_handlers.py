from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from observability.action_audit_log import ActionAuditLog
from entrypoints.api.request_context import RequestContext
from entrypoints.api.webhook_security_surface_guard import WebhookSecuritySurfaceGuard
from security.payload_redaction import PayloadRedactor
from security.webhook_signature_verifier import WebhookSignatureVerifier


CANON_API_WEBHOOK_ROUTE_HANDLERS_FINAL_OWNER = True
CANON_API_WEBHOOK_ROUTE_HANDLERS = True


@dataclass(frozen=True, kw_only=True)
class WebhookRouteHandlers:
    verifier: WebhookSignatureVerifier
    audit_log: ActionAuditLog = field(default_factory=ActionAuditLog)
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    security_guard: WebhookSecuritySurfaceGuard

    def receive(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
        tenant_id: str | None = None,
        connector_id: str | None = None,
        request_context: RequestContext | None = None,
    ) -> dict[str, Any]:
        verification = self.verifier.verify(
            headers=headers,
            body=body,
            tenant_id=tenant_id,
            connector_id=connector_id,
        )
        payload_preview = self.payload_redactor.redact({
            'headers': dict(headers),
            'body_text_preview': bytes(body)[:2048].decode('utf-8', errors='replace'),
        })
        derived_request_context = request_context or RequestContext.from_headers(headers)
        security_verdict: dict[str, Any] | None = None
        if verification.verified:
            try:
                security_verdict = self.security_guard.enforce(
                    verification=verification,
                    request_context=derived_request_context,
                    tenant_id=tenant_id,
                    connector_id=connector_id,
                    body=body,
                    headers=headers,
                )
            except PermissionError as exc:
                verification = type(verification)(
                    verified=False,
                    reason=str(exc),
                    key_id=verification.key_id,
                    content_digest=verification.content_digest,
                    metadata=dict(verification.metadata),
                )
        self.audit_log.record({
            'kind': 'webhook',
            'tenant_id': tenant_id,
            'connector_id': connector_id,
            'verified': verification.verified,
            'reason': verification.reason,
            'key_id': verification.key_id,
            'content_digest': verification.content_digest,
            'payload_preview': payload_preview,
            'security_verdict': security_verdict,
        })
        return {
            'accepted': verification.verified,
            'reason': verification.reason,
            'key_id': verification.key_id,
            'content_digest': verification.content_digest,
            'metadata': dict(verification.metadata),
            'security_verdict': security_verdict,
        }


__all__ = [
    'CANON_API_WEBHOOK_ROUTE_HANDLERS',
    'WebhookRouteHandlers',
]
