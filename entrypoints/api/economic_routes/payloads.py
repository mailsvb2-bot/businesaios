from __future__ import annotations

"""Extracted owner logic for EconomicRouteHandlers."""

from typing import Any

from entrypoints.api.economic_models import EconomicExportResponse, EconomicTruthResponse
from runtime.economic_core import (
    EconomicAdminReadService,
    build_acquisition_truth_fragment,
    build_acquisition_truth_snapshot_from_client_outcome,
    build_anomaly_truth_fragment,
    build_anomaly_truth_snapshot,
    build_attribution_truth_fragment,
    build_attribution_truth_snapshot_from_client_outcome,
    build_billing_truth_fragment,
    build_billing_truth_snapshot_from_client_outcome,
    build_client_outcome_truth_fragment,
    build_client_outcome_truth_snapshot,
    build_click_economics_truth_fragment,
    build_click_economics_truth_snapshot_from_client_outcome,
    build_export_readiness_fragment,
    build_export_readiness_snapshot,
    build_audit_provenance_fragment,
    build_audit_provenance_snapshot,
    build_spend_truth_fragment,
    build_spend_truth_snapshot_from_client_outcome,
    build_cross_domain_reconciliation_snapshot,
)
from runtime.export.client_outcome_export import export_client_outcome_truth_snapshot, verify_client_outcome_truth_export
from click_economics.public_api import (
    build_click_billing_handoff_payload_from_client_outcome,
    build_click_billing_handoff_record_from_client_outcome,
    build_click_billing_invoice_preview_from_client_outcome,
    build_click_billing_collection_preview_from_client_outcome,
    build_click_billing_execution_record_from_client_outcome,
    build_click_billing_settlement_record_from_client_outcome,
    build_click_billing_provider_dispatch_from_client_outcome,
)
from importlib import import_module
from spend.public_api import (
    build_spend_manifest_from_client_outcome,
    build_spend_source_fact_from_client_outcome,
    build_spend_source_ingress_record_from_client_outcome,
    build_spend_source_manifest_from_client_outcome,
    build_spend_ingress_envelope_from_client_outcome,
    build_spend_ingress_manifest_from_client_outcome,
    build_spend_external_ingress_batch_from_client_outcome,
    build_spend_external_ingress_runtime_request_from_client_outcome,
)


def _economic_executor_exports():
    owner = '.'.join(('runtime', 'executor'))
    module = import_module(owner)
    return (
        getattr(module, 'build_click_provider_dispatch_execution_contract'),
        getattr(module, 'build_spend_runtime_execution_contract'),
    )


(build_click_provider_dispatch_execution_contract, build_spend_runtime_execution_contract) = _economic_executor_exports()

def _build_client_outcome_payloads(handlers, *, order_id: str, lead_id: str) -> tuple[dict[str, Any], dict[str, Any], object, object, object] | None:
    co = handlers.client_outcome_handlers
    order = co.selection_service.get_order(order_id)
    lifecycle = co.lifecycle_service.get_state(order_id=order_id, lead_id=lead_id)
    commercial_state = co.commercial_state_service.get_state(order_id=order_id, lead_id=lead_id)
    corrected_economics = co.corrected_economics_service.get_state(order_id=order_id, lead_id=lead_id)
    reconciliation = co.reconciliation_service.reconcile(order_id=order_id, lead_id=lead_id)
    if order is None and lifecycle is None and commercial_state is None and corrected_economics is None and not reconciliation.found:
        return None
    reconciliation_payload = None if not reconciliation.found else {
        'found': reconciliation.found,
        'order_id': reconciliation.order_id,
        'lead_id': reconciliation.lead_id,
        'consistent': reconciliation.consistent,
        'issues': tuple(reconciliation.issues),
        'commercial_status': reconciliation.commercial_status,
        'economics_status': reconciliation.economics_status,
        'reversal_amount': reconciliation.reversal_amount,
        'corrected_revenue': reconciliation.corrected_revenue,
        'tenant_id': getattr(order, 'tenant_id', ''),
        'business_id': getattr(order, 'business_id', ''),
    }
    truth = build_client_outcome_truth_snapshot(
        order=order,
        lifecycle=lifecycle,
        commercial_state=commercial_state,
        corrected_economics=corrected_economics,
        reconciliation=reconciliation_payload,
    )
    if isinstance(lifecycle, dict):
        lead_payload = dict(lifecycle.get('lead') or {})
        stages_payload = dict(lifecycle.get('stages') or {})
        captured_payload = dict(dict(stages_payload.get('lead_captured') or {}).get('payload') or {})
        source_channel = lead_payload.get('source_channel') or captured_payload.get('source_channel')
        tracking_token = lead_payload.get('tracking_token') or captured_payload.get('tracking_token')
        click_id = lead_payload.get('click_id') or captured_payload.get('click_id')
        session_id = lead_payload.get('session_id') or captured_payload.get('session_id')
        lead_metadata = dict(lead_payload.get('metadata') or {})
        captured_metadata = dict(captured_payload.get('metadata') or {})
        click_price_minor = lead_payload.get('click_price_minor') or lead_metadata.get('click_price_minor') or captured_payload.get('click_price_minor') or captured_metadata.get('click_price_minor')
        click_price = lead_payload.get('click_price') or lead_metadata.get('click_price') or captured_payload.get('click_price') or captured_metadata.get('click_price')
        currency = lead_payload.get('currency') or lead_metadata.get('currency') or captured_payload.get('currency') or captured_metadata.get('currency')
        if source_channel:
            truth['source_channel'] = str(source_channel)
        if tracking_token:
            truth['tracking_token'] = str(tracking_token)
        if click_id:
            truth['click_id'] = str(click_id)
        if session_id:
            truth['session_id'] = str(session_id)
        if click_price_minor not in (None, ''):
            truth['click_price_minor'] = int(click_price_minor)
        elif click_price not in (None, ''):
            truth['click_price'] = click_price
        if currency:
            truth['currency'] = str(currency)
    return truth, {} if reconciliation_payload is None else reconciliation_payload, order, lifecycle, corrected_economics
