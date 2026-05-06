from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from adapters.api.fastapi.public_routes import register_public_api_routes
from entrypoints.api.api_handler_bundle import build_api_handler_bundle
from entrypoints.api.health_handler import HealthHandler
from entrypoints.api.economic_route_handlers import build_economic_route_handlers
from entrypoints.api.public_surface_security_guard import PublicSurfaceSecurityGuard
from entrypoints.api.request_context import RequestContext


class _StubAppService:
    pass


class _PermissiveGuard(PublicSurfaceSecurityGuard):
    def __init__(self):
        pass

    def enforce(self, *, route_path, request_context: RequestContext, body=None):
        return None


def _build_client() -> TestClient:
    router = APIRouter()
    bundle = build_api_handler_bundle(application_service=_StubAppService())
    register_public_api_routes(
        router=router,
        dependency_container=None,
        health_handler=HealthHandler(application_service=_StubAppService()),
        handlers=bundle.route_handlers,
        headless_handlers=bundle.headless_handlers,
        governance_handlers=None,
        business_memory_handlers=bundle.business_memory_handlers,
        governance_advanced_handlers=None,
        client_outcome_handlers=bundle.client_outcome_handlers,
        economic_handlers=build_economic_route_handlers(client_outcome_handlers=bundle.client_outcome_handlers),
        security_guard=_PermissiveGuard(),
        analytics_handlers=None,
    )
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_full_cycle_persists_commercial_state_and_reads_it() -> None:
    client = _build_client()
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    response = client.post('/client-outcome/full-cycle', json={
        'tenant_id': 'tenant-1',
        'business_id': 'biz-1',
        'package_id': 'clients-1',
        'metadata': {'source': 'test'},
        'lead': {
            'lead_id': 'lead-state-1',
            'captured_at': now,
            'tracking_token': 'trk-1',
            'source_channel': 'ads',
            'phone_hash': 'phone-a',
        },
        'proofs': [{
            'proof_id': 'proof-1',
            'occurred_at': now,
            'proof_type': 'booking_confirmed',
            'status': 'confirmed',
            'source': 'crm',
            'external_ref': 'crm:deal:1',
        }],
        'acquisition_cost': 20.0,
        'dispute_reason_code': 'duplicate_client',
        'dispute_opened_by': 'owner-1',
    })
    assert response.status_code == 200, response.text
    body = response.json()
    order_id = body['order']['order_id']
    lead_id = 'lead-state-1'

    state_response = client.get(f'/client-outcome/commercial-state/{order_id}/{lead_id}')
    assert state_response.status_code == 200, state_response.text
    state = state_response.json()
    assert state['found'] is True
    assert state['commercial_status'] == 'reversed'
    assert state['verification']['billable'] is True
    assert state['revenue_before_reversal']['billed_revenue'] > 0
    assert state['revenue_after_reversal']['billed_revenue'] == 0.0
    assert state['admin_summary']['reversed_clients'] == 1
