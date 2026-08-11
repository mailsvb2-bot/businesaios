from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import APIRouter, HTTPException

from adapters.api.fastapi import business_workspace_acquisition_routes as acquisition_routes
from adapters.api.fastapi import router_support
from governance.rbac_contract import RoleId


def _principal(*, roles=(RoleId.OWNER,), scopes=()):
    return SimpleNamespace(
        tenant_id='tenant-session',
        subject='owner-user',
        actor_id='owner-user',
        roles=roles,
        scopes=scopes,
        metadata={'business_id': 'business-session', 'principal_kind': 'user'},
    )


def _route(router: APIRouter):
    for route in router.routes:
        if getattr(route, 'path', None) == '/business-workspace/acquisition-plan' and 'POST' in getattr(route, 'methods', set()):
            return route.endpoint
    raise AssertionError('acquisition route not found')


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


def test_acquisition_plan_rejects_invalid_payload(monkeypatch) -> None:
    router = APIRouter()
    acquisition_routes.register_business_workspace_acquisition_routes(router=router, auth_bundle=object())
    monkeypatch.setattr(acquisition_routes, 'business_owner_scope', lambda **_: (_principal(), 'tenant-session', 'business-session'))

    async def fake_json_body(_request):
        return {'target_customers': 10}

    monkeypatch.setattr(acquisition_routes, 'json_body', fake_json_body)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_route(router)(object()))
    assert exc.value.status_code == 422


def test_acquisition_plan_json_projection_is_safe_for_unbounded_timeline() -> None:
    assert acquisition_routes._json_safe(float('inf')) is None
    assert acquisition_routes._json_safe({'days': float('-inf'), 'rows': (1, 2)}) == {'days': None, 'rows': [1, 2]}
