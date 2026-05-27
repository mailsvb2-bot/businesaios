from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
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
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _record_payload() -> dict[str, object]:
    return {
        'record_id': 'billable:1',
        'tenant_id': 'tenant-1',
        'business_id': 'biz-1',
        'order_id': 'order-1',
        'lead_id': 'lead-1',
        'package_id': 'clients-5',
        'verified_at': datetime(2026, 4, 13, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
        'unit_price': 70.0,
        'currency': 'EUR',
        'quantity': 1,
        'metadata': {},
    }


def test_open_reverse_and_admin_summary_routes() -> None:
    client = _build_client()

    opened = client.post('/client-outcome/disputes/open', json={
        'tenant_id': 'tenant-1',
        'business_id': 'biz-1',
        'order_id': 'order-1',
        'lead_id': 'lead-1',
        'opened_by': 'owner-1',
        'reason_code': 'missing_proof',
        'record': _record_payload(),
        'metadata': {},
    })
    assert opened.status_code == 200, opened.text
    opened_body = opened.json()
    assert opened_body['classification_case_type'] == 'evidence_gap_review'

    reversed_resp = client.post('/client-outcome/disputes/reverse', json={
        'dispute_id': opened_body['dispute_id'],
        'record': _record_payload(),
    })
    assert reversed_resp.status_code == 200, reversed_resp.text
    reversed_body = reversed_resp.json()
    assert reversed_body['status'] in ('reversed', 'expired')
    is_reversed = reversed_body['status'] == 'reversed'
    if is_reversed:
        assert reversed_body['ledger_posting_id']
    else:
        assert reversed_body.get('ledger_posting_id') in (None, '')

    summary = client.post('/client-outcome/admin-summary', json={
        'order': {
            'order_id': 'order-1', 'tenant_id': 'tenant-1', 'business_id': 'biz-1',
            'package_id': 'clients-5', 'package_label': '5 clients', 'requested_clients': 5,
            'price_per_verified_client': 70.0, 'currency': 'EUR', 'trust_tier': 'tier1_crm',
            'created_at': datetime(2026, 4, 13, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
        },
        'economic_snapshot': {
            'verified_clients': 1, 'billable_clients': 1, 'billed_revenue': 70.0,
            'acquisition_cost': 20.0, 'gross_margin': 50.0, 'cac': 20.0,
            'revenue_per_client': 70.0, 'margin_per_client': 50.0, 'currency': 'EUR',
        },
    })
    assert summary.status_code == 200, summary.text
    summary_body = summary.json()
    if is_reversed:
        assert summary_body['reversed_clients'] == 1
    else:
        assert summary_body['reversed_clients'] == 0
    assert len(summary_body['widgets']) == 3
