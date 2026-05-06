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

def get_click_economics_truth(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return EconomicTruthResponse(found=False)
    truth, _recon, _order, lifecycle, _corrected = payloads
    click_truth = build_click_economics_truth_snapshot_from_client_outcome(truth_snapshot=truth, lifecycle=lifecycle)
    click_fragment = build_click_economics_truth_fragment(click_snapshot=click_truth)
    read_model = handlers.admin_read_service.build_read_model(
        scope_type='click_economics',
        scope_id=order_id,
        tenant_id=click_fragment.tenant_id,
        business_id=click_fragment.business_id,
        truth_payload={'click_economics': click_truth},
        truth_fragment=click_fragment,
        fragments=(),
        extra_widgets=(
            {'widget_id': 'economic_click_widget', 'kind': 'economic_click', 'payload': click_truth},
            {'widget_id': 'economic_click_billable_widget', 'kind': 'economic_click_billable', 'payload': click_truth.get('click_billable_fact')},
            {'widget_id': 'economic_click_handoff_widget', 'kind': 'economic_click_handoff', 'payload': build_click_billing_handoff_payload_from_client_outcome(truth_snapshot=truth, lifecycle=lifecycle)},
        ),
    )
    return EconomicTruthResponse(found=True, **read_model)


def export_click_economics_truth(handlers, *, order_id: str, lead_id: str) -> EconomicExportResponse:
    read_model = handlers.get_click_economics_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicExportResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    return EconomicExportResponse(
        found=True,
        scope_type='click_economics',
        scope_id=order_id,
        algorithm=str(exported['algorithm']),
        hash=str(exported['hash']),
        verified=verify_client_outcome_truth_export(exported),
        export_ready=bool(read_model.snapshot.get('ready_for_export')),
        payload=exported,
    )


def get_click_economics_audit(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers.get_click_economics_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicTruthResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    audit_payload = {
        'algorithm': str(exported['algorithm']),
        'hash': str(exported['hash']),
        'verified': verify_client_outcome_truth_export(exported),
        'domains_with_evidence': ('click_economics',),
        'billable_fact_ready': bool(((read_model.truth or {}).get('click_economics') or {}).get('click_billable_fact_ready')),
    }
    return EconomicTruthResponse(found=True, scope_type='click_economics_audit', scope_id=order_id, tenant_id=str(read_model.tenant_id), business_id=str(read_model.business_id), truth={'audit_provenance': audit_payload}, snapshot=read_model.snapshot, widgets=read_model.widgets)


def get_click_economics_handoff(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return EconomicTruthResponse(found=False)
    truth, _recon, _order, lifecycle, _corrected = payloads
    handoff = build_click_billing_handoff_payload_from_client_outcome(truth_snapshot=truth, lifecycle=lifecycle)
    return EconomicTruthResponse(
        found=True,
        scope_type='click_economics_handoff',
        scope_id=order_id,
        tenant_id=str(handoff.get('tenant_id') or ''),
        business_id=str(handoff.get('business_id') or ''),
        truth={'click_handoff': handoff},
        snapshot={'scope_type': 'click_economics_handoff', 'scope_id': order_id, 'domains': ('click_economics',), 'ready_for_export': bool(handoff.get('ready_for_export'))},
        widgets=({'widget_id': 'economic_click_handoff_widget', 'kind': 'economic_click_handoff', 'payload': handoff},),
    )
