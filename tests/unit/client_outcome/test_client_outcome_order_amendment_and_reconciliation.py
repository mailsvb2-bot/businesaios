from __future__ import annotations

from datetime import UTC, datetime

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


def test_order_can_be_amended_without_creating_new_order() -> None:
    client = _build_client()
    selected = client.post('/client-outcome/select', json={
        'tenant_id': 'tenant-1',
        'business_id': 'biz-1',
        'package_id': 'clients-1',
        'metadata': {'source': 'test'},
    })
    assert selected.status_code == 200, selected.text
    order_id = selected.json()['order_id']

    amended = client.post(f'/client-outcome/orders/{order_id}/amend', json={
        'package_id': 'clients-5',
        'metadata': {'reason': 'upsell'},
    })
    assert amended.status_code == 200, amended.text
    payload = amended.json()
    assert payload['order']['order_id'] == order_id
    assert payload['order']['package_id'] == 'clients-5'
    assert payload['amendment_count'] == 1
    assert payload['amendments'][0]['from_package_id'] == 'clients-1'
    assert payload['amendments'][0]['to_package_id'] == 'clients-5'
    assert payload['amendments'][0]['metadata']['reason'] == 'upsell'

    loaded = client.get(f'/client-outcome/orders/{order_id}')
    assert loaded.status_code == 200, loaded.text
    loaded_payload = loaded.json()
    assert loaded_payload['found'] is True
    assert loaded_payload['order']['order_id'] == order_id
    assert loaded_payload['order']['package_id'] == 'clients-5'


def test_reconciliation_surface_reports_consistent_full_cycle() -> None:
    client = _build_client()
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC).isoformat()
    response = client.post('/client-outcome/full-cycle', json={
        'tenant_id': 'tenant-1',
        'business_id': 'biz-1',
        'package_id': 'clients-1',
        'metadata': {'source': 'test', 'invoice_id': 'inv-100', 'provider_name': 'demo'},
        'lead': {
            'lead_id': 'lead-recon-1',
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
    assert response.status_code == 200, response.text
    order_id = response.json()['order']['order_id']

    reconciliation = client.get(f'/client-outcome/reconciliation/{order_id}/lead-recon-1')
    assert reconciliation.status_code == 200, reconciliation.text
    payload = reconciliation.json()
    assert payload['found'] is True
    assert payload['consistent'] is True
    assert payload['issues'] == []
    assert payload['reversal_amount'] == 25.0
    assert payload['corrected_revenue']['billed_revenue'] == response.json()['revenue_after_reversal']['billed_revenue']


def test_duplicate_amendment_is_idempotent() -> None:
    client = _build_client()
    selected = client.post('/client-outcome/select', json={
        'tenant_id': 'tenant-1',
        'business_id': 'biz-1',
        'package_id': 'clients-1',
    })
    assert selected.status_code == 200, selected.text
    order_id = selected.json()['order_id']

    amended1 = client.post(f'/client-outcome/orders/{order_id}/amend', json={'package_id': 'clients-5'})
    amended2 = client.post(f'/client-outcome/orders/{order_id}/amend', json={'package_id': 'clients-5'})
    assert amended1.status_code == 200, amended1.text
    assert amended2.status_code == 200, amended2.text
    payload = amended2.json()
    assert payload['order']['package_id'] == 'clients-5'
    assert payload['amendment_count'] == 1
    assert len(payload['amendments']) == 1


def test_amendment_is_denied_after_billing_started() -> None:
    client = _build_client()
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC).isoformat()
    response = client.post('/client-outcome/full-cycle', json={
        'tenant_id': 'tenant-1',
        'business_id': 'biz-1',
        'package_id': 'clients-1',
        'lead': {
            'lead_id': 'lead-no-amend',
            'captured_at': now,
            'tracking_token': 'trk-na',
            'source_channel': 'ads',
            'phone_hash': 'phone-na',
        },
        'proofs': [{
            'proof_id': 'proof-na',
            'occurred_at': now,
            'proof_type': 'booking_confirmed',
            'status': 'confirmed',
            'source': 'crm',
            'external_ref': 'crm:deal:no-amend',
        }],
        'acquisition_cost': 20.0,
    })
    assert response.status_code == 200, response.text
    order_id = response.json()['order']['order_id']

    amend = client.post(f'/client-outcome/orders/{order_id}/amend', json={'package_id': 'clients-5'})
    assert amend.status_code == 409, amend.text
    assert 'amendment_not_allowed_for_current_commercial_state' in amend.text


def test_admin_view_surface_contains_timeline_and_reconciliation_widgets() -> None:
    client = _build_client()
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC).isoformat()
    response = client.post('/client-outcome/full-cycle', json={
        'tenant_id': 'tenant-1',
        'business_id': 'biz-1',
        'package_id': 'clients-1',
        'metadata': {'invoice_id': 'inv-admin', 'provider_name': 'demo'},
        'lead': {
            'lead_id': 'lead-admin-view',
            'captured_at': now,
            'tracking_token': 'trk-admin',
            'source_channel': 'ads',
            'phone_hash': 'phone-admin',
            'metadata': {'invoice_id': 'inv-admin', 'provider_name': 'demo'},
        },
        'proofs': [{
            'proof_id': 'proof-admin',
            'occurred_at': now,
            'proof_type': 'booking_confirmed',
            'status': 'confirmed',
            'source': 'crm',
            'external_ref': 'crm:deal:admin',
        }],
        'acquisition_cost': 20.0,
        'dispute_reason_code': 'manual_operator_review',
        'dispute_opened_by': 'owner-1',
        'dispute_reversal_amount': 25.0,
    })
    assert response.status_code == 200, response.text
    order_id = response.json()['order']['order_id']
    admin_view = client.get(f'/client-outcome/orders/{order_id}/lead-admin-view/admin-view')
    assert admin_view.status_code == 200, admin_view.text
    payload = admin_view.json()
    assert payload['found'] is True
    widget_ids = {item['widget_id'] for item in payload['widgets']}
    assert 'client_outcome_timeline' in widget_ids
    assert 'client_outcome_reconciliation' in widget_ids
    assert payload['reconciliation']['consistent'] is True
    assert 'corrected_economics' in payload['lifecycle']['stages']
    assert 'refund_requested' in payload['lifecycle']['stages']
    refund_widget = {item['widget_id']: item for item in payload['widgets']}['client_outcome_refund_bridge']
    assert refund_widget['payload']['has_refund_request'] is True


def test_reconciliation_reports_missing_dispute_stage_when_truth_is_inconsistent() -> None:
    from entrypoints.api.client_outcome_route_handlers import build_client_outcome_route_handlers

    handlers = build_client_outcome_route_handlers()
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC)
    handlers.commercial_state_service.store.upsert_state(
        order_id='order-inconsistent',
        lead_id='lead-inconsistent',
        now=now,
        patch={
            'commercial_status': 'disputed',
            'dispute': {'dispute_id': 'disp-1', 'status': 'open'},
            'revenue_before_reversal': {'billed_revenue': 25.0, 'billable_clients': 1, 'verified_clients': 1, 'currency': 'USD'},
            'revenue_after_reversal': {'billed_revenue': 25.0, 'billable_clients': 1, 'verified_clients': 1, 'currency': 'USD'},
        },
    )
    handlers.corrected_economics_service.store.upsert_state(
        order_id='order-inconsistent',
        lead_id='lead-inconsistent',
        now=now,
        patch={
            'economics_status': 'uncorrected',
            'corrected_revenue': {'billed_revenue': 25.0, 'billable_clients': 1, 'verified_clients': 1, 'currency': 'USD'},
        },
    )
    handlers.lifecycle_service.store.upsert_stage(
        order_id='order-inconsistent',
        lead_id='lead-inconsistent',
        stage_name='selected_and_executed',
        now=now,
        stage_payload={'status': 'ok'},
    )
    handlers.lifecycle_service.store.upsert_stage(
        order_id='order-inconsistent',
        lead_id='lead-inconsistent',
        stage_name='verified',
        now=now,
        stage_payload={'status': 'ok'},
    )
    handlers.lifecycle_service.store.upsert_stage(
        order_id='order-inconsistent',
        lead_id='lead-inconsistent',
        stage_name='billed',
        now=now,
        stage_payload={'status': 'ok'},
    )

    result = handlers.reconciliation_service.reconcile(order_id='order-inconsistent', lead_id='lead-inconsistent')
    assert result.found is True
    assert result.consistent is False
    assert 'missing_lifecycle_dispute_opened_stage' in result.issues


def test_admin_view_surface_contains_operator_and_anomaly_widgets() -> None:
    client = _build_client()
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC).isoformat()
    selected = client.post('/client-outcome/select', json={
        'tenant_id': 'tenant-1',
        'business_id': 'biz-1',
        'package_id': 'clients-1',
        'metadata': {'source': 'test'},
    })
    assert selected.status_code == 200, selected.text
    order_id = selected.json()['order_id']
    amended = client.post(f'/client-outcome/orders/{order_id}/amend', json={'package_id': 'clients-5'})
    assert amended.status_code == 200, amended.text

    admin_view = client.get(f'/client-outcome/orders/{order_id}/lead-missing/admin-view')
    assert admin_view.status_code == 200, admin_view.text
    payload = admin_view.json()
    assert payload['found'] is True
    widget_ids = {item['widget_id'] for item in payload['widgets']}
    assert 'client_outcome_operator_actions' in widget_ids
    assert 'client_outcome_anomalies' in widget_ids
    widgets = {item['widget_id']: item for item in payload['widgets']}
    assert widgets['client_outcome_operator_actions']['payload']['allowed_actions']
    assert widgets['client_outcome_anomalies']['payload']['severity'] == 'attention_required'


def test_reconciliation_reports_missing_refund_requested_stage_when_refund_truth_is_inconsistent() -> None:
    from entrypoints.api.client_outcome_route_handlers import build_client_outcome_route_handlers

    handlers = build_client_outcome_route_handlers()
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC)
    handlers.commercial_state_service.store.upsert_state(
        order_id='order-refund-inconsistent',
        lead_id='lead-refund-inconsistent',
        now=now,
        patch={
            'commercial_status': 'reversed',
            'dispute': {'dispute_id': 'disp-2', 'status': 'accepted'},
            'reversal': {'reversal_id': 'rev-2', 'amount': 25.0, 'currency': 'USD'},
            'revenue_before_reversal': {'billed_revenue': 25.0, 'billable_clients': 1, 'verified_clients': 1, 'currency': 'USD'},
            'revenue_after_reversal': {'billed_revenue': 0.0, 'billable_clients': 0, 'verified_clients': 1, 'currency': 'USD'},
        },
    )
    handlers.corrected_economics_service.store.upsert_state(
        order_id='order-refund-inconsistent',
        lead_id='lead-refund-inconsistent',
        now=now,
        patch={
            'economics_status': 'corrected',
            'corrected_revenue': {'billed_revenue': 0.0, 'billable_clients': 0, 'verified_clients': 1, 'currency': 'USD'},
            'reversal': {'reversal_id': 'rev-2', 'amount': 25.0, 'currency': 'USD'},
            'refund_preview': {'amount_minor': 2500, 'currency': 'USD'},
            'refund_request': {'amount_minor': 2500, 'currency': 'USD', 'invoice_id': 'inv-2', 'provider_name': 'demo'},
        },
    )
    for stage_name in ('selected_and_executed', 'verified', 'billed', 'dispute_opened', 'reversed', 'corrected_economics'):
        handlers.lifecycle_service.store.upsert_stage(
            order_id='order-refund-inconsistent',
            lead_id='lead-refund-inconsistent',
            stage_name=stage_name,
            now=now,
            stage_payload={'status': 'ok'},
        )

    result = handlers.reconciliation_service.reconcile(order_id='order-refund-inconsistent', lead_id='lead-refund-inconsistent')
    assert result.found is True
    assert result.consistent is False
    assert 'missing_lifecycle_refund_requested_stage' in result.issues


def test_admin_view_surface_contains_recovery_and_metrics_widgets() -> None:
    client = _build_client()
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC).isoformat()
    response = client.post('/client-outcome/full-cycle', json={
        'tenant_id': 'tenant-1',
        'business_id': 'biz-1',
        'package_id': 'clients-1',
        'metadata': {'invoice_id': 'inv-metrics', 'provider_name': 'demo'},
        'lead': {
            'lead_id': 'lead-metrics-view',
            'captured_at': now,
            'tracking_token': 'trk-metrics',
            'source_channel': 'ads',
            'phone_hash': 'phone-metrics',
            'metadata': {'invoice_id': 'inv-metrics', 'provider_name': 'demo'},
        },
        'proofs': [{
            'proof_id': 'proof-metrics',
            'occurred_at': now,
            'proof_type': 'booking_confirmed',
            'status': 'confirmed',
            'source': 'crm',
            'external_ref': 'crm:deal:metrics',
        }],
        'acquisition_cost': 20.0,
        'dispute_reason_code': 'manual_operator_review',
        'dispute_opened_by': 'owner-1',
        'dispute_reversal_amount': 25.0,
    })
    assert response.status_code == 200, response.text
    order_id = response.json()['order']['order_id']

    admin_view = client.get(f'/client-outcome/orders/{order_id}/lead-metrics-view/admin-view')
    assert admin_view.status_code == 200, admin_view.text
    payload = admin_view.json()
    widgets = {item['widget_id']: item for item in payload['widgets']}
    assert 'client_outcome_recovery_bridge' in widgets
    assert 'client_outcome_operational_metrics' in widgets
    assert widgets['client_outcome_recovery_bridge']['payload']['export_ready'] is True
    metrics_payload = widgets['client_outcome_operational_metrics']['payload']
    assert metrics_payload['tenant_id'] == 'tenant-1'
    assert metrics_payload['metrics']['client_outcome.reconciliation_consistent']['value'] == 1.0
    assert metrics_payload['metrics']['client_outcome.reconciliation_issue_count']['value'] == 0.0


def test_reconciliation_endpoint_emits_metrics_for_inconsistent_truth() -> None:
    from entrypoints.api.client_outcome_route_handlers import build_client_outcome_route_handlers

    handlers = build_client_outcome_route_handlers()
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC)
    handlers.commercial_state_service.store.upsert_state(
        order_id='order-metric-inconsistent',
        lead_id='lead-metric-inconsistent',
        now=now,
        patch={
            'tenant_id': 'tenant-metric',
            'commercial_status': 'reversed',
            'dispute': {'dispute_id': 'disp-metric', 'status': 'accepted'},
            'reversal': {'reversal_id': 'rev-metric', 'amount': 25.0, 'currency': 'USD'},
            'revenue_before_reversal': {'billed_revenue': 25.0, 'billable_clients': 1, 'verified_clients': 1, 'currency': 'USD'},
            'revenue_after_reversal': {'billed_revenue': 0.0, 'billable_clients': 0, 'verified_clients': 1, 'currency': 'USD'},
        },
    )
    handlers.corrected_economics_service.store.upsert_state(
        order_id='order-metric-inconsistent',
        lead_id='lead-metric-inconsistent',
        now=now,
        patch={
            'tenant_id': 'tenant-metric',
            'economics_status': 'corrected',
            'corrected_revenue': {'billed_revenue': 0.0, 'billable_clients': 0, 'verified_clients': 1, 'currency': 'USD'},
            'reversal': {'reversal_id': 'rev-metric', 'amount': 25.0, 'currency': 'USD'},
            'refund_preview': {'amount_minor': 2500, 'currency': 'USD'},
        },
    )
    for stage_name in ('selected_and_executed', 'verified', 'billed', 'dispute_opened', 'reversed', 'corrected_economics'):
        handlers.lifecycle_service.store.upsert_stage(
            order_id='order-metric-inconsistent',
            lead_id='lead-metric-inconsistent',
            stage_name=stage_name,
            now=now,
            stage_payload={'status': 'ok', 'tenant_id': 'tenant-metric'},
        )

    result = handlers.get_reconciliation(order_id='order-metric-inconsistent', lead_id='lead-metric-inconsistent')
    assert result.found is True
    assert result.consistent is False
    consistent_metric = handlers.tenant_metrics_registry.metric_snapshot(tenant_id='tenant-metric', metric_name='client_outcome.reconciliation_consistent')
    issue_metric = handlers.tenant_metrics_registry.metric_snapshot(tenant_id='tenant-metric', metric_name='client_outcome.reconciliation_issue_count')
    observed_metric = handlers.tenant_metrics_registry.metric_snapshot(tenant_id='tenant-metric', metric_name='client_outcome.reconciliation_issues_observed')
    assert consistent_metric is not None and consistent_metric['value'] == 0.0
    assert issue_metric is not None and issue_metric['value'] >= 1.0
    assert observed_metric is not None and observed_metric['value'] >= 1.0
