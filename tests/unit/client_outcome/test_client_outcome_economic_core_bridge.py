from __future__ import annotations

from datetime import datetime, timezone, UTC

from entrypoints.api.client_outcome_route_handlers import build_client_outcome_route_handlers
from lock.economic_truth_lock import validate_no_economic_truth_bypass
from runtime.economic_core.client_outcome_bridge import build_client_outcome_truth_snapshot
from runtime.export.client_outcome_export import (
    export_client_outcome_truth_snapshot,
    verify_client_outcome_truth_export,
)


def test_client_outcome_truth_snapshot_and_export_are_deterministic() -> None:
    handlers = build_client_outcome_route_handlers()
    now = datetime(2026, 4, 14, 10, 0, 0, tzinfo=UTC)
    selection = handlers.selection_service.select(
        now=now,
        request=__import__('lead_outcomes.client_outcome_selection_service', fromlist=['ClientOutcomeSelectionInput']).ClientOutcomeSelectionInput(
            tenant_id='tenant-truth',
            business_id='biz-truth',
            package_id='clients-1',
            requested_clients=None,
            metadata={'source': 'test'},
        ),
    )
    order = selection.order
    handlers.commercial_state_service.store.upsert_state(
        order_id=order.order_id,
        lead_id='lead-truth',
        now=now,
        patch={
            'tenant_id': 'tenant-truth',
            'commercial_status': 'reversed',
            'dispute': {'dispute_id': 'disp-truth', 'status': 'accepted'},
            'reversal': {'reversal_id': 'rev-truth', 'amount': 25.0, 'currency': 'USD'},
            'revenue_before_reversal': {'billed_revenue': 25.0, 'billable_clients': 1, 'verified_clients': 1, 'currency': 'USD'},
            'revenue_after_reversal': {'billed_revenue': 0.0, 'billable_clients': 0, 'verified_clients': 1, 'currency': 'USD'},
        },
    )
    handlers.corrected_economics_service.store.upsert_state(
        order_id=order.order_id,
        lead_id='lead-truth',
        now=now,
        patch={
            'tenant_id': 'tenant-truth',
            'economics_status': 'corrected',
            'corrected_revenue': {'billed_revenue': 0.0, 'billable_clients': 0, 'verified_clients': 1, 'currency': 'USD'},
            'reversal': {'reversal_id': 'rev-truth', 'amount': 25.0, 'currency': 'USD'},
            'refund_preview': {'amount_minor': 2500, 'currency': 'USD'},
            'refund_request': {'amount_minor': 2500, 'currency': 'USD', 'invoice_id': 'inv-truth', 'provider_name': 'demo'},
        },
    )
    for stage_name in ('selected_and_executed', 'verified', 'billed', 'dispute_opened', 'reversed', 'corrected_economics', 'refund_requested'):
        handlers.lifecycle_service.store.upsert_stage(
            order_id=order.order_id,
            lead_id='lead-truth',
            stage_name=stage_name,
            now=now,
            stage_payload={'status': 'ok', 'tenant_id': 'tenant-truth'},
        )

    reconciliation = handlers.reconciliation_service.reconcile(order_id=order.order_id, lead_id='lead-truth')
    payload = {
        'found': reconciliation.found,
        'order_id': reconciliation.order_id,
        'lead_id': reconciliation.lead_id,
        'consistent': reconciliation.consistent,
        'issues': tuple(reconciliation.issues),
        'commercial_status': reconciliation.commercial_status,
        'economics_status': reconciliation.economics_status,
        'reversal_amount': reconciliation.reversal_amount,
    }
    snapshot = build_client_outcome_truth_snapshot(
        order=order,
        lifecycle=handlers.lifecycle_service.get_state(order_id=order.order_id, lead_id='lead-truth'),
        commercial_state=handlers.commercial_state_service.get_state(order_id=order.order_id, lead_id='lead-truth'),
        corrected_economics=handlers.corrected_economics_service.get_state(order_id=order.order_id, lead_id='lead-truth'),
        reconciliation=payload,
    )
    exported = export_client_outcome_truth_snapshot(snapshot)

    assert snapshot['reconciliation_consistent'] is True
    assert snapshot['final_truth_revenue'] == 0.0
    assert exported['algorithm'] == 'sha256'
    assert verify_client_outcome_truth_export(exported) is True


def test_admin_view_contains_economic_truth_and_export_widgets() -> None:
    from tests.unit.client_outcome.test_client_outcome_order_amendment_and_reconciliation import _build_client

    client = _build_client()
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC).isoformat()
    response = client.post('/client-outcome/full-cycle', json={
        'tenant_id': 'tenant-1',
        'business_id': 'biz-1',
        'package_id': 'clients-1',
        'metadata': {'invoice_id': 'inv-export', 'provider_name': 'demo'},
        'lead': {
            'lead_id': 'lead-export-view',
            'captured_at': now,
            'tracking_token': 'trk-export',
            'source_channel': 'ads',
            'phone_hash': 'phone-export',
            'metadata': {'invoice_id': 'inv-export', 'provider_name': 'demo'},
        },
        'proofs': [{
            'proof_id': 'proof-export',
            'occurred_at': now,
            'proof_type': 'booking_confirmed',
            'status': 'confirmed',
            'source': 'crm',
            'external_ref': 'crm:deal:export',
        }],
        'acquisition_cost': 20.0,
        'dispute_reason_code': 'manual_operator_review',
        'dispute_opened_by': 'owner-1',
        'dispute_reversal_amount': 25.0,
    })
    assert response.status_code == 200, response.text
    order_id = response.json()['order']['order_id']
    admin_view = client.get(f'/client-outcome/orders/{order_id}/lead-export-view/admin-view')
    assert admin_view.status_code == 200, admin_view.text
    widgets = {item['widget_id']: item for item in admin_view.json()['widgets']}
    assert 'client_outcome_economic_truth' in widgets
    assert 'client_outcome_export_bundle' in widgets
    assert widgets['client_outcome_economic_truth']['payload']['reconciliation_consistent'] is True
    assert widgets['client_outcome_export_bundle']['payload']['verified'] is True
    assert widgets['client_outcome_export_bundle']['payload']['export_ready'] is True


def test_economic_truth_lock_rejects_bypass_markers() -> None:
    try:
        validate_no_economic_truth_bypass('manual reversal logic')
    except RuntimeError as exc:
        assert 'Economic truth bypass detected' in str(exc)
    else:
        raise AssertionError('expected lock to reject bypass markers')
