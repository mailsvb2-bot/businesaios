from __future__ import annotations

from datetime import datetime, timezone, UTC

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


def test_full_cycle_route_returns_corrected_economics() -> None:
    client = _build_client()
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC).isoformat()
    response = client.post('/client-outcome/full-cycle', json={
        'tenant_id': 'tenant-1',
        'business_id': 'biz-1',
        'package_id': 'clients-1',
        'metadata': {'source': 'test'},
        'lead': {
            'lead_id': 'lead-1',
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
    assert body['verification']['billable'] is True
    assert body['revenue_before_reversal']['billed_revenue'] > 0
    assert body['reversal']['ledger_posting_id']
    assert body['revenue_after_reversal']['billed_revenue'] == 0.0
    assert body['admin_summary']['reversed_clients'] == 1


def test_full_cycle_route_supports_partial_reversal_and_refund_preview() -> None:
    client = _build_client()
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC).isoformat()
    response = client.post('/client-outcome/full-cycle', json={
        'tenant_id': 'tenant-1',
        'business_id': 'biz-1',
        'package_id': 'clients-1',
        'metadata': {'source': 'test', 'invoice_id': 'inv-1', 'provider_name': 'demo'},
        'lead': {
            'lead_id': 'lead-partial',
            'captured_at': now,
            'tracking_token': 'trk-p',
            'source_channel': 'ads',
            'phone_hash': 'phone-p',
            'metadata': {'invoice_id': 'inv-1', 'provider_name': 'demo'},
        },
        'proofs': [{
            'proof_id': 'proof-p',
            'occurred_at': now,
            'proof_type': 'booking_confirmed',
            'status': 'confirmed',
            'source': 'crm',
            'external_ref': 'crm:deal:partial',
        }],
        'acquisition_cost': 20.0,
        'dispute_reason_code': 'manual_operator_review',
        'dispute_opened_by': 'owner-1',
        'dispute_reversal_amount': 25.0,
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['reversal']['partial_reversal'] is True
    assert body['reversal']['amount'] == 25.0
    assert body['reversal']['refund_preview']['invoice_id'] == 'inv-1'
    assert body['revenue_after_reversal']['billed_revenue'] > 0.0
    assert body['revenue_after_reversal']['billed_revenue'] < body['revenue_before_reversal']['billed_revenue']
