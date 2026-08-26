from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import APIRouter, HTTPException

from adapters.api.fastapi import business_workspace_provider_routes as workspace
from adapters.api.fastapi import router_support
from governance.rbac_contract import RoleId


class _Handlers:
    def __init__(self, providers=()) -> None:
        self.activated = None
        self.sync_called = False
        self.providers = list(providers)

    def list_provider_catalog(self, *, tenant_id: str, business_id: str):
        return {'tenant_id': tenant_id, 'business_id': business_id, 'providers': list(self.providers)}

    def activate_provider(self, *, payload):
        self.activated = dict(payload)
        return {'ok': True, 'tenant_id': payload['tenant_id'], 'business_id': payload['business_id']}

    def probe_provider_live(self, **kwargs):
        return dict(kwargs)

    def trigger_provider_sync(self, *, payload):
        self.sync_called = True
        return dict(payload)

    def list_provider_sync_history(self, **kwargs):
        return dict(kwargs)


def _principal(*, roles=(RoleId.OWNER,), scopes=('provider_control_plane',)):
    return SimpleNamespace(tenant_id='tenant-session', subject='owner-user', actor_id='owner-user', roles=roles, scopes=scopes, metadata={'business_id': 'business-session', 'principal_kind': 'user'})


def _route(router: APIRouter, method: str):
    for route in router.routes:
        if getattr(route, 'path', None) == '/business-workspace/providers' and method in getattr(route, 'methods', set()):
            return route.endpoint
    raise AssertionError(f'route not found: {method}')


def _truth_rows():
    return {
        'contract-provider': SimpleNamespace(status='contract_only', read_only_supported=True, read_capabilities=('read',), required_credentials=()),
        'partial-provider': SimpleNamespace(status='partial', read_only_supported=True, read_capabilities=('read',), required_credentials=()),
        'hubspot': SimpleNamespace(status='partial', read_only_supported=True, read_capabilities=('contact_sync', 'deal_sync'), required_credentials=('access_token',)),
    }


def _authenticate_as(monkeypatch, principal) -> None:
    monkeypatch.setattr(router_support, 'authorize_request', lambda **_: (object(), principal))


def test_workspace_scope_requires_owner_and_provider_scope(monkeypatch) -> None:
    _authenticate_as(monkeypatch, _principal())
    _, tenant_id, business_id = workspace._workspace_scope(request=object(), auth_bundle=object())
    assert (tenant_id, business_id) == ('tenant-session', 'business-session')
    for principal in (_principal(roles=()), _principal(scopes=())):
        _authenticate_as(monkeypatch, principal)
        with pytest.raises(HTTPException) as exc:
            workspace._workspace_scope(request=object(), auth_bundle=object())
        assert exc.value.status_code == 403


def test_customer_catalog_fails_closed_for_contract_only_read_plan(monkeypatch) -> None:
    handlers = _Handlers(({'provider_key': 'contract-provider'}, {'provider_key': 'partial-provider'}))
    router = APIRouter()
    workspace.register_business_workspace_provider_routes(router=router, auth_bundle=object(), provider_admin_handlers=handlers)
    _authenticate_as(monkeypatch, _principal())
    monkeypatch.setattr(workspace, 'provider_truth_map', _truth_rows)
    result = asyncio.run(_route(router, 'GET')(object()))
    rows = {row['provider_key']: row for row in result['providers']}
    assert rows['contract-provider']['customer_selectable'] is False
    assert rows['partial-provider']['customer_selectable'] is True
    assert result['write_actions_enabled'] is False


def test_activation_ignores_browser_workspace_identity_and_ownership(monkeypatch) -> None:
    handlers = _Handlers()
    router = APIRouter()
    workspace.register_business_workspace_provider_routes(router=router, auth_bundle=object(), provider_admin_handlers=handlers)
    _authenticate_as(monkeypatch, _principal())
    monkeypatch.setattr(workspace, 'provider_truth_map', _truth_rows)

    async def fake_json_body(_request):
        return {'action': 'activate', 'tenant_id': 'tenant-victim', 'business_id': 'business-victim', 'ownership_key': 'attacker-owned', 'requested_by': 'attacker', 'provider_key': 'hubspot', 'external_ref': 'portal-123', 'secrets': {'access_token': 'secret-value'}}

    monkeypatch.setattr(workspace, 'json_body', fake_json_body)
    result = asyncio.run(_route(router, 'POST')(object()))
    assert result['ok'] is True
    assert handlers.activated['tenant_id'] == 'tenant-session'
    assert handlers.activated['business_id'] == 'business-session'
    assert handlers.activated['ownership_key'] == 'owner:owner-user:hubspot'
    assert handlers.activated['requested_by'] == 'owner-user'


def test_write_operation_is_rejected_before_provider_runtime(monkeypatch) -> None:
    handlers = _Handlers()
    router = APIRouter()
    workspace.register_business_workspace_provider_routes(router=router, auth_bundle=object(), provider_admin_handlers=handlers)
    _authenticate_as(monkeypatch, _principal())
    monkeypatch.setattr(workspace, 'provider_truth_map', _truth_rows)

    async def fake_json_body(_request):
        return {'action': 'read', 'provider_key': 'hubspot', 'operation': 'message_send', 'mode': 'live', 'payload': {'tenant_id': 'tenant-victim'}}

    monkeypatch.setattr(workspace, 'json_body', fake_json_body)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_route(router, 'POST')(object()))
    assert exc.value.status_code == 403
    assert handlers.sync_called is False


def test_activation_validation_tracks_entire_provider_truth_matrix(monkeypatch) -> None:
    handlers, router = _Handlers(), APIRouter()
    workspace.register_business_workspace_provider_routes(router=router, auth_bundle=object(), provider_admin_handlers=handlers)
    _authenticate_as(monkeypatch, _principal())
    endpoint, truth_rows = _route(router, 'POST'), workspace.provider_truth_map()

    for provider_key, truth in sorted(truth_rows.items()):
        ready = bool(truth.read_only_supported) and str(truth.status) in workspace._READY
        supplied = {name: f'matrix-{provider_key}-{name}' for name in truth.required_credentials}
        cases = ({}, *({key: value for key, value in supplied.items() if key != missing} for missing in truth.required_credentials))
        for secrets in cases:
            handlers.activated = None

            async def fake_json_body(_request, payload={'action': 'activate', 'provider_key': provider_key, 'external_ref': 'matrix-ref', 'secrets': secrets}):
                return payload

            monkeypatch.setattr(workspace, 'json_body', fake_json_body)
            if not ready:
                with pytest.raises(HTTPException) as exc:
                    asyncio.run(endpoint(object()))
                assert exc.value.status_code == 409
            elif truth.required_credentials:
                with pytest.raises(HTTPException) as exc:
                    asyncio.run(endpoint(object()))
                assert (exc.value.status_code, exc.value.detail) == (422, 'provider_required_credentials_missing')
                assert handlers.activated is None
            else:
                assert asyncio.run(endpoint(object()))['ok'] is True

        if ready and truth.required_credentials:
            async def complete_json_body(_request, payload={'action': 'activate', 'provider_key': provider_key, 'external_ref': 'matrix-ref', 'secrets': supplied}):
                return payload

            monkeypatch.setattr(workspace, 'json_body', complete_json_body)
            assert asyncio.run(endpoint(object()))['ok'] is True
            assert handlers.activated['secrets'] == supplied

    ready_key = next(key for key, truth in truth_rows.items() if truth.read_only_supported and str(truth.status) in workspace._READY)

    async def invalid_json_body(_request):
        return {'action': 'activate', 'provider_key': ready_key, 'external_ref': 'matrix-ref', 'secrets': ['not', 'a', 'mapping']}

    monkeypatch.setattr(workspace, 'json_body', invalid_json_body)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(object()))
    assert (exc.value.status_code, exc.value.detail) == (422, 'provider_secrets_invalid')
