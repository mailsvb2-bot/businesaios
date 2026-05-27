from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from adapters.api.fastapi.public_routes import register_public_api_routes
from entrypoints.api.api_handler_bundle import build_api_handler_bundle
from entrypoints.api.economic_route_handlers import build_economic_route_handlers
from entrypoints.api.health_handler import HealthHandler
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


def test_full_cycle_persists_lifecycle_chain() -> None:
    client = _build_client()
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    response = client.post('/client-outcome/full-cycle', json={
        'tenant_id': 'tenant-1',
        'business_id': 'biz-1',
        'package_id': 'clients-1',
        'metadata': {'source': 'test'},
        'lead': {
            'lead_id': 'lead-42',
            'captured_at': now,
            'tracking_token': 'trk-42',
            'source_channel': 'ads',
            'phone_hash': 'phone-z',
        },
        'proofs': [{
            'proof_id': 'proof-42',
            'occurred_at': now,
            'proof_type': 'booking_confirmed',
            'status': 'confirmed',
            'source': 'crm',
            'external_ref': 'crm:deal:42',
        }],
        'acquisition_cost': 15.0,
        'dispute_reason_code': 'duplicate_client',
        'dispute_opened_by': 'owner-1',
    })
    assert response.status_code == 200, response.text
    order_id = response.json()['order']['order_id']

    lifecycle = client.get(f'/client-outcome/lifecycle/{order_id}/lead-42')
    assert lifecycle.status_code == 200, lifecycle.text
    body = lifecycle.json()
    assert body['found'] is True
    stages = body['stages']
    assert 'selected_and_executed' in stages
    assert 'verified' in stages
    assert 'billed' in stages
    assert 'dispute_opened' in stages
    assert 'reversed' in stages
    assert 'corrected_economics' in stages
    assert stages['corrected_economics']['payload']['billed_revenue'] == 0.0
