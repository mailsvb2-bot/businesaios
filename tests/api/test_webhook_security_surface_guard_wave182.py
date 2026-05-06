from __future__ import annotations

from datetime import datetime, timezone

from entrypoints.api.request_context import RequestContext
from entrypoints.api.webhook_security_surface_guard import WebhookSecuritySurfaceGuard
from security.webhook_signature_verifier import WebhookVerificationResult


def test_webhook_security_surface_guard_denies_unencrypted_transport() -> None:
    guard = WebhookSecuritySurfaceGuard.default()
    verification = WebhookVerificationResult(
        verified=True,
        reason='verified',
        key_id='webhook-v1',
        content_digest='abc',
        metadata={'algorithm': 'hmac-sha256'},
    )
    try:
        guard.enforce(
            verification=verification,
            request_context=RequestContext(tenant_id='tenant-a', metadata={'transport_encrypted': False}),
            tenant_id='tenant-a',
            connector_id='crm',
            body=b'{}',
            headers={'content-type': 'application/json'},
        )
    except PermissionError as exc:
        assert str(exc) == 'encryption_required'
    else:
        raise AssertionError('expected PermissionError')


def test_webhook_security_surface_guard_allows_verified_https_request() -> None:
    guard = WebhookSecuritySurfaceGuard.default()
    verification = WebhookVerificationResult(
        verified=True,
        reason='verified',
        key_id='webhook-v1',
        content_digest='abc',
        metadata={'algorithm': 'hmac-sha256'},
    )
    verdict = guard.enforce(
        verification=verification,
        request_context=RequestContext(tenant_id='tenant-a', metadata={'transport_encrypted': True, 'region_hint': 'eu'}),
        tenant_id='tenant-a',
        connector_id='crm',
        body=b'{"ok": true}',
        headers={'content-type': 'application/json'},
    )
    assert verdict['allowed'] is True
    assert verdict['reason'] == 'allowed'
