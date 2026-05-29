from __future__ import annotations

from datetime import datetime, timedelta, timezone, UTC

from app.web.auth import AuthService
from app.web.session import SessionStore
from entrypoints.api.request_context import RequestContext
from interfaces.api.fastapi_dependencies import FastAPIDependencyContainer
from security.payload_redaction import PayloadRedactor
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


def test_request_context_from_headers_and_redaction() -> None:
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
    assert redacted['ip_address'] == '<redacted>'
    assert ctx.tenant_context(required=True).tenant_id == 'tenant-1'


def test_fastapi_dependencies_build_request_context_and_keep_boot_contract() -> None:
    container = FastAPIDependencyContainer(boot_result=_BootResult())
    ctx = container.request_context({'X-Request-Id': 'req-2'})
    assert ctx.request_id == 'req-2'
    assert container.tenant_context({'X-Tenant-Id': 'tenant-2'}, required=True).tenant_id == 'tenant-2'
    assert container.application_service() is container.boot_result.decision_application
