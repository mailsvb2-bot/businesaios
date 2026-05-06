from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from governance.rbac_contract import RoleId
from entrypoints.api.api_key_policy import ApiKeyPolicy, InMemoryApiKeyStore
from adapters.api.fastapi.auth_dependencies import AuthDependencyBundle, CompositeAuthPolicy
from entrypoints.api.jwt_policy import JwtClaims, JwtPolicy
from entrypoints.api.request_context import RequestContext
from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle


def _request(headers: dict[str, str] | None = None) -> Request:
    raw_headers = [(k.lower().encode('latin-1'), v.encode('latin-1')) for k, v in (headers or {}).items()]
    scope = {'type': 'http', 'method': 'GET', 'path': '/', 'headers': raw_headers}
    return Request(scope)


def _security_guard():
    return ApiSecurityOwnerBundle.default(audit_path='runtime/data/security/test_auth_dependencies_owner_audit.jsonl').api_surface_guard


def test_auth_dependencies_accept_api_key_principal() -> None:
    store = InMemoryApiKeyStore()
    record, raw_key = store.issue(tenant_id='tenant-a', subject='svc-billing', roles=(RoleId.SYSTEM,))
    bundle = AuthDependencyBundle(auth_policy=CompositeAuthPolicy(api_key_policy=ApiKeyPolicy(store=store)), security_guard=_security_guard())

    principal = bundle.authenticate(
        request=_request({'X-API-Key': raw_key}),
        request_context=RequestContext(tenant_id='tenant-a'),
        authorization=None,
        x_api_key=raw_key,
    )

    assert principal.subject == record.subject
    assert principal.tenant_id == 'tenant-a'
    assert principal.metadata['auth_type'] == 'api_key'


def test_auth_dependencies_reject_ambiguous_mechanisms() -> None:
    store = InMemoryApiKeyStore()
    _, raw_key = store.issue(tenant_id='tenant-a', subject='svc-billing')
    jwt = JwtPolicy(secret='test-secret', audience='api')
    token = jwt.issue(JwtClaims(subject='alice', tenant_id='tenant-a', audience='api', roles=(RoleId.OWNER,)))
    bundle = AuthDependencyBundle(
        auth_policy=CompositeAuthPolicy(api_key_policy=ApiKeyPolicy(store=store), jwt_policy=jwt, allow_multiple_mechanisms=False),
        security_guard=_security_guard(),
    )

    with pytest.raises(HTTPException) as exc:
        bundle.authenticate(
            request=_request({'Authorization': f'Bearer {token}', 'X-API-Key': raw_key}),
            request_context=RequestContext(tenant_id='tenant-a'),
            authorization=f'Bearer {token}',
            x_api_key=raw_key,
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == 'ambiguous_authentication_mechanisms'


def test_auth_dependencies_reject_missing_authentication_fail_closed() -> None:
    bundle = AuthDependencyBundle(auth_policy=CompositeAuthPolicy(), security_guard=_security_guard())

    with pytest.raises(HTTPException) as exc:
        bundle.authenticate(
            request=_request(),
            request_context=RequestContext(tenant_id='tenant-a'),
            authorization=None,
            x_api_key=None,
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == 'missing_authentication'


def test_auth_dependencies_reject_tenant_mismatch_from_jwt() -> None:
    jwt = JwtPolicy(secret='test-secret', audience='api')
    token = jwt.issue(JwtClaims(subject='alice', tenant_id='tenant-a', audience='api', roles=(RoleId.OWNER,)))
    bundle = AuthDependencyBundle(auth_policy=CompositeAuthPolicy(jwt_policy=jwt), security_guard=_security_guard())

    with pytest.raises(HTTPException) as exc:
        bundle.authenticate(
            request=_request({'Authorization': f'Bearer {token}'}),
            request_context=RequestContext(tenant_id='tenant-b'),
            authorization=f'Bearer {token}',
            x_api_key=None,
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == 'tenant_mismatch'
