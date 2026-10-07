from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import APIRouter, HTTPException

from adapters.api.fastapi import business_workspace_acquisition_routes as acquisition_routes
from adapters.api.fastapi import router_support
from governance.rbac_contract import RoleId



class _LandingState:
    def __init__(self, *, published: bool) -> None:
        self._published = published

    def public_content(self):
        return {"ok": True} if self._published else None


class _LandingRegistry:
    def __init__(self, *, published: bool = True) -> None:
        self.published = published
        self.calls = []

    def get(self, **kwargs):
        self.calls.append(dict(kwargs))
        return _LandingState(published=self.published)


def _principal(*, roles=(RoleId.OWNER,), scopes=()):
    return SimpleNamespace(
        tenant_id='tenant-session',
        subject='owner-user',
        actor_id='owner-user',
        roles=roles,
        scopes=scopes,
        metadata={'business_id': 'business-session', 'principal_kind': 'user'},
    )


def _route(router: APIRouter, path: str = '/business-workspace/acquisition-plan'):
    for route in router.routes:
        if getattr(route, 'path', None) == path and 'POST' in getattr(route, 'methods', set()):
            return route.endpoint
    raise AssertionError(f'route not found: {path}')


def _payload() -> dict:
    return {
        'tenant_id': 'tenant-attacker',
        'business_id': 'business-attacker',
        'target_customers': 10,
        'total_budget': 300,
        'daily_budget': 20,
        'target_days': 30,
        'cost_per_entry': 10,
        'gross_margin_ltv': 300,
        'expected_monthly_margin_per_customer': 50,
        'stages': [{'name': 'lead_to_customer', 'conversion_rate': 0.5, 'avg_stage_days': 3, 'touchpoints': 1}],
    }


def test_owner_business_scope_does_not_require_provider_scope(monkeypatch) -> None:
    monkeypatch.setattr(router_support, 'authorize_request', lambda **_: (object(), _principal(scopes=())))
    _, tenant_id, business_id = router_support.business_owner_scope(request=object(), auth_bundle=object())
    assert (tenant_id, business_id) == ('tenant-session', 'business-session')
    monkeypatch.setattr(router_support, 'authorize_request', lambda **_: (object(), _principal(roles=())))
    with pytest.raises(HTTPException) as exc:
        router_support.business_owner_scope(request=object(), auth_bundle=object())
    assert exc.value.status_code == 403


def test_acquisition_plan_uses_session_scope_and_canonical_solver(monkeypatch) -> None:
    router = APIRouter()
    acquisition_routes.register_business_workspace_acquisition_routes(router=router, auth_bundle=object())
    monkeypatch.setattr(acquisition_routes, 'business_owner_scope', lambda **_: (_principal(), 'tenant-session', 'business-session'))

    async def fake_json_body(_request):
        return _payload()

    monkeypatch.setattr(acquisition_routes, 'json_body', fake_json_body)
    result = asyncio.run(_route(router)(object()))
    assert result['tenant_id'] == 'tenant-session'
    assert result['business_id'] == 'business-session'
    assert result['assumption_source'] == 'owner_input'
    assert result['calculation_only'] is True
    assert result['write_actions_enabled'] is False
    assert result['plan']['feasible'] is True
    assert result['plan']['achievable_customers'] >= 10
    assert result['economics']['overall_conversion_rate'] == 0.5
    assert result['economics']['sustainable'] is True
    assert result['economics']['blended_cac'] == 30.0


def test_acquisition_plan_rejects_invalid_or_overflowing_payload(monkeypatch) -> None:
    router = APIRouter()
    acquisition_routes.register_business_workspace_acquisition_routes(router=router, auth_bundle=object())
    monkeypatch.setattr(acquisition_routes, 'business_owner_scope', lambda **_: (_principal(), 'tenant-session', 'business-session'))
    for body in ({'target_customers': 10}, {**_payload(), 'target_customers': float('inf')}):
        async def fake_json_body(_request, payload=body):
            return payload

        monkeypatch.setattr(acquisition_routes, 'json_body', fake_json_body)
        with pytest.raises(HTTPException) as exc:
            asyncio.run(_route(router)(object()))
        assert exc.value.status_code == 422


def test_acquisition_plan_json_projection_is_safe_for_unbounded_timeline() -> None:
    assert acquisition_routes._json_safe(float('inf')) is None
    assert acquisition_routes._json_safe({'days': float('-inf'), 'rows': (1, 2)}) == {'days': None, 'rows': [1, 2]}


def test_event_promotion_target_uses_authenticated_scope_and_live_public_route(monkeypatch) -> None:
    router = APIRouter()
    landing_registry = _LandingRegistry()
    acquisition_routes.register_business_workspace_acquisition_routes(router=router, auth_bundle=object(), event_landing_registry=landing_registry)
    monkeypatch.setattr(acquisition_routes, 'business_owner_scope', lambda **_: (_principal(), 'tenant-session', 'business-session'))

    async def fake_json_body(_request):
        return {
            'tenant_id': 'tenant-attacker',
            'business_id': 'business-attacker',
            'event_id': 'event-123',
            'public_base_url': 'https://business.example.test',
        }

    monkeypatch.setattr(acquisition_routes, 'json_body', fake_json_body)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_route(router, '/business-workspace/event-promotion-target')(object()))
    assert (exc.value.status_code, exc.value.detail) == (422, 'event_promotion_unknown_fields')

    async def clean_body(_request):
        return {'event_id': 'event-123', 'public_base_url': 'https://business.example.test'}

    monkeypatch.setattr(acquisition_routes, 'json_body', clean_body)
    result = asyncio.run(_route(router, '/business-workspace/event-promotion-target')(object()))
    assert result['tenant_id'] == 'tenant-session'
    assert result['business_id'] == 'business-session'
    assert result['destination_url'] == (
        'https://business.example.test/public-site/events/tenant-session/business-session/event-123'
        '?source=ads&campaign_ref=event%3Aevent-123'
    )
    assert result['calculation_only'] is True
    assert result['write_actions_enabled'] is False
    assert landing_registry.calls == [{'tenant_id': 'tenant-session', 'business_id': 'business-session', 'event_id': 'event-123'}]


def test_event_promotion_target_rejects_unpublished_event(monkeypatch) -> None:
    router = APIRouter()
    acquisition_routes.register_business_workspace_acquisition_routes(
        router=router,
        auth_bundle=object(),
        event_landing_registry=_LandingRegistry(published=False),
    )
    monkeypatch.setattr(acquisition_routes, 'business_owner_scope', lambda **_: (_principal(), 'tenant-session', 'business-session'))

    async def body(_request):
        return {'event_id': 'event-draft', 'public_base_url': 'https://business.example.test'}

    monkeypatch.setattr(acquisition_routes, 'json_body', body)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_route(router, '/business-workspace/event-promotion-target')(object()))
    assert (exc.value.status_code, exc.value.detail) == (409, 'event_landing_not_published')


def test_event_promotion_target_fails_closed_when_landing_registry_unavailable(monkeypatch) -> None:
    router = APIRouter()
    acquisition_routes.register_business_workspace_acquisition_routes(
        router=router,
        auth_bundle=object(),
        event_landing_registry=None,
    )
    monkeypatch.setattr(acquisition_routes, 'business_owner_scope', lambda **_: (_principal(), 'tenant-session', 'business-session'))

    async def body(_request):
        return {'event_id': 'event-123', 'public_base_url': 'https://business.example.test'}

    monkeypatch.setattr(acquisition_routes, 'json_body', body)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_route(router, '/business-workspace/event-promotion-target')(object()))
    assert (exc.value.status_code, exc.value.detail) == (503, 'event_landing_registry_unavailable')
