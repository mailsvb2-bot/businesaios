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


def test_corrected_economics_route_exposes_refund_request_bridge() -> None:
    client = _build_client()
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    response = client.post('/client-outcome/full-cycle', json={
        'tenant_id': 'tenant-1',
        'business_id': 'biz-1',
        'package_id': 'clients-1',
        'metadata': {'source': 'test', 'invoice_id': 'inv-100', 'provider_name': 'demo'},
        'lead': {
            'lead_id': 'lead-corrected-1',
            'captured_at': now,
            'tracking_token': 'trk-100',
            'source_channel': 'ads',
            'phone_hash': 'phone-z',
            'metadata': {'invoice_id': 'inv-100', 'provider_name': 'demo'},
        },
        'proofs': [{
            'proof_id': 'proof-100',
            'occurred_at': now,
            'proof_type': 'booking_confirmed',
            'status': 'confirmed',
            'source': 'crm',
            'external_ref': 'crm:deal:100',
        }],
        'acquisition_cost': 20.0,
        'dispute_reason_code': 'manual_operator_review',
        'dispute_opened_by': 'owner-1',
        'dispute_reversal_amount': 25.0,
    })
    body = response.json()
    order_id = body['order']['order_id']

    corrected = client.get(f'/client-outcome/corrected-economics/{order_id}/lead-corrected-1')
    assert corrected.status_code == 200, corrected.text
    payload = corrected.json()
    assert payload['found'] is True
    assert payload['economics_status'] == 'corrected'
    assert payload['refund_preview']['invoice_id'] == 'inv-100'
    assert payload['refund_request']['invoice_id'] == 'inv-100'
    assert payload['refund_request']['amount_minor'] == 2500


def test_full_cycle_idempotency_key_replays_same_response_without_duplication() -> None:
    client = _build_client()
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    request = {
        'tenant_id': 'tenant-1',
        'business_id': 'biz-1',
        'package_id': 'clients-1',
        'metadata': {'source': 'test'},
        'lead': {
            'lead_id': 'lead-idem-1',
            'captured_at': now,
            'tracking_token': 'trk-idem',
            'source_channel': 'ads',
            'phone_hash': 'phone-idem',
        },
        'proofs': [{
            'proof_id': 'proof-idem',
            'occurred_at': now,
            'proof_type': 'booking_confirmed',
            'status': 'confirmed',
            'source': 'crm',
            'external_ref': 'crm:deal:idem',
        }],
        'acquisition_cost': 20.0,
        'idempotency_key': 'idem-1',
    }
    first = client.post('/client-outcome/full-cycle', json=request)
    second = client.post('/client-outcome/full-cycle', json=request)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json() == second.json()
