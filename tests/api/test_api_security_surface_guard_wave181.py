from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from governance.rbac_contract import RoleId
from entrypoints.api.api_key_policy import ApiKeyPolicy, InMemoryApiKeyStore
from adapters.api.fastapi.auth_dependencies import AuthDependencyBundle, CompositeAuthPolicy
from entrypoints.api.auth_contract import AuthPrincipal
from entrypoints.api.jwt_policy import JwtClaims, JwtPolicy
from entrypoints.api.request_context import RequestContext
from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle
from entrypoints.api.tenant_route_guards import TenantRouteGuard


def _request(headers: dict[str, str] | None = None) -> Request:
    raw_headers = [(k.lower().encode('latin-1'), v.encode('latin-1')) for k, v in (headers or {}).items()]
    scope = {'type': 'http', 'method': 'GET', 'path': '/control', 'headers': raw_headers}
    return Request(scope)


def _security_guard():
    return ApiSecurityOwnerBundle.default(audit_path='runtime/data/security/test_api_security_surface_guard_wave181.jsonl').api_surface_guard


def test_jwt_policy_exposes_security_metadata_for_surface_guard() -> None:
    jwt = JwtPolicy(secret='test-secret', audience='api')
    token = jwt.issue(JwtClaims(subject='alice', tenant_id='tenant-a', audience='api', roles=(RoleId.OWNER,)))
    verdict = jwt.authenticate(type('Req', (), {'tenant_id': 'tenant-a', 'authorization': f'Bearer {token}', 'validate': lambda self: None})())
    assert verdict.allowed is True
    assert verdict.principal is not None
    assert verdict.principal.metadata['auth_type'] == 'jwt'
    assert 'issued_at' in verdict.principal.metadata
    assert 'expires_at' in verdict.principal.metadata
    assert verdict.principal.metadata['algorithm'] == 'HS256'


def test_auth_dependencies_fail_closed_when_transport_not_encrypted() -> None:
    store = InMemoryApiKeyStore()
    _, raw_key = store.issue(tenant_id='tenant-a', subject='svc-billing', roles=(RoleId.SYSTEM,))
    bundle = AuthDependencyBundle(auth_policy=CompositeAuthPolicy(api_key_policy=ApiKeyPolicy(store=store)), security_guard=_security_guard())

    with pytest.raises(HTTPException) as exc:
        bundle.authenticate(
            request=_request({'X-API-Key': raw_key}),
            request_context=RequestContext(tenant_id='tenant-a', metadata={'transport_encrypted': False}),
            authorization=None,
            x_api_key=raw_key,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == 'encryption_required'


def test_tenant_route_guard_uses_security_guard_for_binding_mismatch() -> None:
    now = datetime.now(timezone.utc)
    principal = AuthPrincipal(
        subject='alice',
        tenant_id='tenant-a',
        actor_id='alice',
        roles=(RoleId.OWNER,),
        metadata={
            'auth_type': 'jwt',
            'issued_at': (now - timedelta(minutes=1)).isoformat(),
            'expires_at': (now + timedelta(minutes=9)).isoformat(),
            'bound_ip': '10.0.0.1',
        },
    )
    guard = TenantRouteGuard(security_guard=_security_guard())

    with pytest.raises(HTTPException) as exc:
        guard.enforce(
            principal=principal,
            request_context=RequestContext(tenant_id='tenant-a', ip_address='10.0.0.2'),
            body={'tenant_id': 'tenant-a'},
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == 'ip_mismatch'
