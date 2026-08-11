from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import APIRouter, HTTPException

from adapters.api.fastapi.public_site_routes import register_public_site_routes
from entrypoints.api.public_surface_route_specs import _ROUTE_SPECS
from security.access_policy import SecurityAction


class _Request:
    def __init__(self, payload) -> None:
        self._payload = payload

    async def json(self):
        return self._payload


def _route(router: APIRouter):
    for route in router.routes:
        if getattr(route, 'path', None) == '/public-site/acquisition/feasibility':
            return route.endpoint
    raise AssertionError('acquisition calculator route not found')


def _payload() -> dict:
    return {
        'target_customers': 10,
        'total_budget': 10000,
        'daily_budget': 1000,
        'target_days': 30,
        'cost_per_entry': 100,
        'gross_margin_ltv': 10000,
        'expected_monthly_margin_per_customer': 2000,
        'setup_cost': 0,
        'max_cac_to_ltv_ratio': 0.33,
        'payback_horizon_months': 12,
        'stages': [{'name': 'lead_to_customer', 'conversion_rate': 0.2, 'avg_stage_days': 5, 'touchpoints': 1}],
    }


def test_acquisition_calculator_uses_public_perimeter_and_canonical_solver() -> None:
    calls = []
    router = APIRouter()

    def security(**kwargs):
        calls.append(kwargs)

    register_public_site_routes(router=router, enforce_public_security=security)
    response = asyncio.run(_route(router)(_Request(_payload())))

    assert calls[-1]['route_path'] == '/public-site/acquisition/feasibility'
    assert response['ok'] is True
    assert response['scenario_source'] == 'user_assumptions'
    assert response['write_actions_enabled'] is False
    assert response['view']['achievable_customers'] >= 0
    assert response['view']['required_budget'] >= 0
    assert response['economics']['feasibility_score'] >= 0
    assert response['economics']['blended_cac'] >= 0
    assert 'не подтверждённые метрики бизнеса' in response['disclaimer']


def test_acquisition_calculator_rejects_invalid_contract() -> None:
    router = APIRouter()
    register_public_site_routes(router=router, enforce_public_security=lambda **_: None)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_route(router)(_Request({'target_customers': 10})))
    assert exc.value.status_code == 422
    assert 'missing required payload fields' in str(exc.value.detail)


def test_acquisition_calculator_has_explicit_read_only_public_security_spec() -> None:
    spec = _ROUTE_SPECS['/public-site/acquisition/feasibility']
    assert spec.action is SecurityAction.READ
    assert 'public' in spec.tags
    assert 'internal' not in spec.tags
    assert spec.resource_type == 'acquisition_scenario'
