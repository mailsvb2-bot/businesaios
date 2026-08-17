from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

from app.web.auth import AuthService
from app.web.session import SessionStore
from entrypoints.api.auth_contract import AuthPrincipal
from entrypoints.api.request_context import RequestContext
from entrypoints.api.security_surface_guard import ApiSecuritySurfaceGuard
from interfaces.api.fastapi_dependencies import FastAPIDependencyContainer
from security.payload_redaction import PayloadRedactor
from security.security_integration_adapter import SecurityIntegrationAdapter
from security.session_policy import SessionPolicy
from security.token_policy import TokenPolicy


class _BootResult:
    def __init__(self) -> None:
        self.decision_application = object()


def test_auth_service_redacts_sensitive_payload() -> None:
    now = datetime.now(UTC)
    payload = {
        'issued_at': (now - timedelta(hours=1)).isoformat(),
        'expires_at': (now + timedelta(hours=23)).isoformat(),
        'subject': 'user-1',
        'audience': 'api',
        'password': 'super-secret',
    }
    result = AuthService(token_policy=TokenPolicy(max_ttl_seconds=172800)).authenticate(payload)
    assert result['kind'] == 'auth_result'
    assert result['payload']['password'] == '***REDACTED***'
    assert result['payload']['security']['token']['allowed'] is True
    assert result['payload']['security']['tenant']['bound'] is False


def test_session_store_fail_closed_when_timestamps_missing() -> None:
    result = SessionStore().build({'session_id': 's1', 'access_token': 'abc'})
    assert result['kind'] == 'session'
    assert result['payload']['access_token'] == '***REDACTED***'
    assert result['payload']['security']['session']['allowed'] is False
    assert result['payload']['security']['session']['invalidate_session'] is True
    assert result['payload']['security']['tenant']['bound'] is False


def test_request_context_from_headers_does_not_trust_forwarded_identity() -> None:
    ctx = RequestContext.from_headers(
        {
            'X-Request-Id': 'req-1',
            'X-Correlation-Id': 'corr-1',
            'X-Tenant-Id': 'tenant-1',
            'X-Forwarded-For': '127.0.0.1',
            'User-Agent': 'pytest',
            'X-Token-Scopes': 'read write',
        },
        metadata={'email': 'user@example.com'},
    )
    redacted = ctx.redacted_dict(redactor=PayloadRedactor())
    assert redacted['request_id'] == 'req-1'
    assert redacted['metadata']['email'] == '<redacted>'
    assert ctx.ip_address is None
    assert redacted['ip_address'] is None
    assert ctx.tenant_context(required=True).tenant_id == 'tenant-1'


def test_fastapi_dependencies_build_request_context_and_keep_boot_contract() -> None:
    container = FastAPIDependencyContainer(boot_result=_BootResult())
    ctx = container.request_context({'X-Request-Id': 'req-2'})
    assert ctx.request_id == 'req-2'
    assert container.tenant_context({'X-Tenant-Id': 'tenant-2'}, required=True).tenant_id == 'tenant-2'
    assert container.application_service() is container.boot_result.decision_application


def test_sessionless_service_api_key_uses_request_time_security_projection() -> None:
    now = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    created_at = now - timedelta(days=7)
    principal = AuthPrincipal(
        subject='production-control-plane-smoke:tenant-live',
        tenant_id='tenant-live',
        actor_id='production-control-plane-smoke:tenant-live',
        scopes=('provider_control_plane',),
        metadata={
            'auth_type': 'api_key',
            'principal_kind': 'service',
            'key_id': 'ak_test',
            'created_at': created_at.isoformat(),
            'issued_at': created_at.isoformat(),
            'session_created_at': created_at.isoformat(),
            'security_now': now.isoformat(),
        },
    )
    guard = ApiSecuritySurfaceGuard(adapter=cast(SecurityIntegrationAdapter, object()))
    request_context = RequestContext(tenant_id='tenant-live')

    auth_payload = guard._build_auth_payload(principal=principal, request_context=request_context)
    session_payload = guard._build_session_payload(principal=principal, request_context=request_context)

    issued_at = datetime.fromisoformat(str(auth_payload['issued_at']))
    expires_at = datetime.fromisoformat(str(auth_payload['expires_at']))
    session_created_at = datetime.fromisoformat(str(session_payload['created_at']))
    session_last_seen_at = datetime.fromisoformat(str(session_payload['last_seen_at']))

    assert issued_at == now
    assert expires_at == now + timedelta(seconds=guard.default_token_ttl_seconds)
    assert session_created_at == now
    assert session_last_seen_at == now
    assert TokenPolicy().evaluate(
        issued_at=issued_at,
        expires_at=expires_at,
        now=now,
        scopes=principal.scopes,
        subject=principal.subject,
        audience=str(auth_payload['audience']),
        issuer=str(auth_payload['issuer']),
        session_id=principal.session_id,
        algorithm=None,
        key_id='ak_test',
    ).allowed is True
    assert SessionPolicy().evaluate(
        created_at=session_created_at,
        last_seen_at=session_last_seen_at,
        now=now,
    ).allowed is True


def test_sessionless_service_api_key_projection_never_outlives_record_expiry() -> None:
    now = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    record_expires_at = now + timedelta(seconds=120)
    principal = AuthPrincipal(
        subject='service',
        tenant_id='tenant-live',
        metadata={
            'auth_type': 'api_key',
            'principal_kind': 'service',
            'key_id': 'ak_test',
            'expires_at': record_expires_at.isoformat(),
            'security_now': now.isoformat(),
        },
    )
    guard = ApiSecuritySurfaceGuard(adapter=cast(SecurityIntegrationAdapter, object()))

    payload = guard._build_auth_payload(principal=principal, request_context=RequestContext(tenant_id='tenant-live'))

    assert datetime.fromisoformat(str(payload['expires_at'])) == record_expires_at
