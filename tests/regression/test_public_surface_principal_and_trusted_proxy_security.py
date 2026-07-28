from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from adapters.api.fastapi.router_support import authorize_request, first_role
from entrypoints.api.auth_contract import AuthPrincipal
from entrypoints.api.public_surface_route_specs import _ROUTE_SPECS
from entrypoints.api.public_surface_security_guard import PublicSurfaceSecurityGuard
from entrypoints.api.request_context import RequestContext
from governance.rbac_contract import RoleId
from security.owner_factory import build_default_security_adapter


class _Headers(dict[str, str]):
    def get(self, key: str, default=None):
        return super().get(str(key).lower(), default)


def _request(*, peer_ip: str, scheme: str = 'http', headers: dict[str, str] | None = None):
    return SimpleNamespace(
        headers=_Headers({str(k).lower(): str(v) for k, v in dict(headers or {}).items()}),
        url=SimpleNamespace(scheme=scheme, path='/test'),
        client=SimpleNamespace(host=peer_ip),
        method='POST',
    )


def _principal(role: RoleId) -> AuthPrincipal:
    return AuthPrincipal(
        subject='signed-subject',
        tenant_id='tenant-a',
        actor_id='signed-actor',
        session_id='signed-session',
        roles=(role,),
        scopes=('scope:a',),
        audience='public-api',
        metadata={'auth_type': 'jwt'},
    )


def _context() -> RequestContext:
    return RequestContext(
        tenant_id='tenant-a',
        actor_id='signed-actor',
        subject='signed-subject',
        ip_address='198.51.100.10',
        metadata={
            'scheme': 'https',
            'transport_encrypted': True,
            'jwt_verified': True,
            'authenticated_principal': True,
            'idempotency_key': 'idem-1',
        },
    )


def test_every_internal_route_requires_external_authentication() -> None:
    guard = PublicSurfaceSecurityGuard.default()
    internal = [path for path, spec in _ROUTE_SPECS.items() if 'internal' in spec.tags]
    assert internal
    assert all(guard.requires_external_auth(path) for path in internal)
    assert not guard.requires_external_auth('/public-site/cta/start')


def test_real_principal_roles_are_preserved_for_rbac(tmp_path) -> None:
    guard = PublicSurfaceSecurityGuard(
        adapter=build_default_security_adapter(audit_path=str(tmp_path / 'audit.jsonl'))
    )
    body = {'tenant_id': 'tenant-a', 'business_id': 'business-a', 'idempotency_key': 'idem-1'}

    with pytest.raises(PermissionError, match='missing_permission'):
        guard.enforce(
            route_path='/goals/execute',
            request_context=_context(),
            body=body,
            principal=_principal(RoleId.FINANCE),
        )

    owner_verdict = guard.enforce(
        route_path='/baselines/promote',
        request_context=_context(),
        body=body,
        principal=_principal(RoleId.OWNER),
    )
    assert owner_verdict['allowed'] is True

    with pytest.raises(PermissionError, match='api_authenticated_principal_required'):
        guard.enforce(
            route_path='/business-memory/get',
            request_context=_context(),
            body={'tenant_id': 'tenant-a', 'business_id': 'business-a'},
        )


def test_authorize_request_discards_spoofed_identity_headers() -> None:
    principal = _principal(RoleId.OWNER)

    class Bundle:
        def authenticate(self, **_kwargs):
            return principal

    request = _request(
        peer_ip='198.51.100.10',
        scheme='https',
        headers={
            'x-actor-id': 'attacker-actor',
            'x-auth-subject': 'attacker-subject',
            'x-tenant-id': 'tenant-a',
            'x-token-scopes': 'attacker:*',
            'authorization': 'Bearer token',
        },
    )
    context, returned = authorize_request(request=request, auth_bundle=Bundle())
    assert returned is principal
    assert context.actor_id == 'signed-actor'
    assert context.subject == 'signed-subject'
    assert context.tenant_id == 'tenant-a'
    assert context.token_scopes == ('scope:a',)


def test_forwarded_transport_headers_require_an_explicit_trusted_proxy(monkeypatch) -> None:
    monkeypatch.delenv('BUSINESAIOS_TRUST_PROXY_HEADERS', raising=False)
    monkeypatch.delenv('BUSINESAIOS_TRUSTED_PROXY_IPS', raising=False)
    untrusted = RequestContext.from_http_request(
        _request(
            peer_ip='203.0.113.9',
            headers={
                'x-forwarded-proto': 'https',
                'x-forwarded-for': '127.0.0.1',
                'user-agent': 'attacker-testclient',
            },
        )
    )
    assert untrusted.ip_address == '203.0.113.9'
    assert untrusted.metadata['transport_encrypted'] is False
    assert untrusted.metadata['forwarded_headers_trusted'] is False

    monkeypatch.setenv('BUSINESAIOS_TRUST_PROXY_HEADERS', '1')
    monkeypatch.setenv('BUSINESAIOS_TRUSTED_PROXY_IPS', '10.0.0.0/8')
    still_untrusted = RequestContext.from_http_request(
        _request(peer_ip='203.0.113.9', headers={'x-forwarded-proto': 'https'})
    )
    assert still_untrusted.metadata['transport_encrypted'] is False

    trusted = RequestContext.from_http_request(
        _request(
            peer_ip='10.1.2.3',
            headers={'x-forwarded-proto': 'https', 'x-forwarded-for': '198.51.100.44'},
        )
    )
    assert trusted.ip_address == '198.51.100.44'
    assert trusted.metadata['transport_encrypted'] is True
    assert trusted.metadata['forwarded_headers_trusted'] is True


def test_empty_principal_roles_fail_closed() -> None:
    with pytest.raises(HTTPException) as exc:
        first_role(AuthPrincipal(subject='subject', tenant_id='tenant-a'))
    assert exc.value.status_code == 403
