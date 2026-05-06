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

def _build_client_outcome_truth(handlers, *, order_id: str, lead_id: str) -> dict[str, Any] | None:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return None
    truth, recon, _order, lifecycle, corrected_economics = payloads
    fragment = build_client_outcome_truth_fragment(truth_snapshot=truth)
    acquisition_truth = build_acquisition_truth_snapshot_from_client_outcome(truth_snapshot=truth)
    acquisition_fragment = build_acquisition_truth_fragment(acquisition_snapshot=acquisition_truth)
    attribution_truth = build_attribution_truth_snapshot_from_client_outcome(truth_snapshot=truth, lifecycle=lifecycle)
    attribution_fragment = build_attribution_truth_fragment(attribution_snapshot=attribution_truth)
    click_truth = build_click_economics_truth_snapshot_from_client_outcome(truth_snapshot=truth, lifecycle=lifecycle)
    click_fragment = build_click_economics_truth_fragment(click_snapshot=click_truth)
    spend_truth = build_spend_truth_snapshot_from_client_outcome(truth_snapshot=truth)
    spend_fragment = build_spend_truth_fragment(spend_snapshot=spend_truth)
    billing_truth = build_billing_truth_snapshot_from_client_outcome(truth_snapshot=truth, corrected_economics=corrected_economics)
    anomaly_truth = build_anomaly_truth_snapshot(reconciliation=recon, billing_snapshot=billing_truth, attribution_snapshot=attribution_truth)
    anomaly_fragment = build_anomaly_truth_fragment(anomaly_snapshot=anomaly_truth)
    export_readiness_truth = build_export_readiness_snapshot(reconciliation=recon, anomaly_snapshot=anomaly_truth)
    export_readiness_fragment = build_export_readiness_fragment(export_readiness_snapshot=export_readiness_truth)
    audit_truth = build_audit_provenance_snapshot(
        truth_payload=truth,
        fragments=(fragment, acquisition_fragment, attribution_fragment, click_fragment, spend_fragment, anomaly_fragment, export_readiness_fragment),
    )
    audit_fragment = build_audit_provenance_fragment(audit_snapshot=audit_truth)
    return handlers.admin_read_service.build_read_model(
        scope_type='client_outcome',
        scope_id=order_id,
        tenant_id=fragment.tenant_id,
        business_id=fragment.business_id,
        truth_fragment=fragment,
        truth_payload=truth,
        fragments=(acquisition_fragment, attribution_fragment, click_fragment, spend_fragment, anomaly_fragment, export_readiness_fragment, audit_fragment),
        extra_widgets=(
            {
                'widget_id': 'economic_acquisition_widget',
                'kind': 'economic_acquisition',
                'payload': {
                    'acquisition_cost': truth.get('acquisition_cost'),
                    'cac': truth.get('cac'),
                    'source_channel': truth.get('source_channel'),
                },
            },
            {
                'widget_id': 'economic_attribution_widget',
                'kind': 'economic_attribution',
                'payload': attribution_truth,
            },
            {
                'widget_id': 'economic_click_widget',
                'kind': 'economic_click',
                'payload': click_truth,
            },
            {
                'widget_id': 'economic_click_billable_widget',
                'kind': 'economic_click_billable',
                'payload': click_truth.get('click_billable_fact'),
            },
            {
                'widget_id': 'economic_spend_widget',
                'kind': 'economic_spend',
                'payload': spend_truth,
            },
            {
                'widget_id': 'economic_spend_owner_widget',
                'kind': 'economic_spend_owner',
                'payload': spend_truth,
            },
            {
                'widget_id': 'economic_anomaly_widget',
                'kind': 'economic_anomaly',
                'payload': anomaly_truth,
            },
            {
                'widget_id': 'economic_export_readiness_widget',
                'kind': 'economic_export_readiness',
                'payload': export_readiness_truth,
            },
            {
                'widget_id': 'economic_audit_provenance_widget',
                'kind': 'economic_audit_provenance',
                'payload': audit_truth,
            },
        ),
    )

def get_client_outcome_truth(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers._build_client_outcome_truth(order_id=order_id, lead_id=lead_id)
    if read_model is None:
        return EconomicTruthResponse(found=False)
    return EconomicTruthResponse(found=True, **read_model)

def export_client_outcome_truth(handlers, *, order_id: str, lead_id: str) -> EconomicExportResponse:
    read_model = handlers._build_client_outcome_truth(order_id=order_id, lead_id=lead_id)
    if read_model is None:
        return EconomicExportResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model['truth'])
    return EconomicExportResponse(
        found=True,
        scope_type='client_outcome',
        scope_id=order_id,
        algorithm=str(exported['algorithm']),
        hash=str(exported['hash']),
        verified=verify_client_outcome_truth_export(exported),
        export_ready=bool(read_model['snapshot'].get('ready_for_export')),
        payload=exported,
    )

def get_client_outcome_audit(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers._build_client_outcome_truth(order_id=order_id, lead_id=lead_id)
    if read_model is None:
        return EconomicTruthResponse(found=False)
    widgets = tuple(item for item in tuple(read_model.get('widgets') or ()) if item.get('widget_id') in {'economic_audit_provenance_widget', 'economic_export_readiness_widget'})
    audit_widget = next((item for item in widgets if item.get('widget_id') == 'economic_audit_provenance_widget'), None)
    export_widget = next((item for item in widgets if item.get('widget_id') == 'economic_export_readiness_widget'), None)
    return EconomicTruthResponse(
        found=True,
        scope_type='client_outcome_audit',
        scope_id=order_id,
        tenant_id=str(read_model.get('tenant_id') or ''),
        business_id=str(read_model.get('business_id') or ''),
        truth={
            'audit_provenance': None if audit_widget is None else audit_widget.get('payload'),
            'export_readiness': None if export_widget is None else export_widget.get('payload'),
        },
        snapshot=read_model.get('snapshot'),
        widgets=widgets,
    )

def get_client_outcome_anomalies(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers._build_client_outcome_truth(order_id=order_id, lead_id=lead_id)
    if read_model is None:
        return EconomicTruthResponse(found=False)
    widgets = tuple(item for item in tuple(read_model.get('widgets') or ()) if item.get('widget_id') in {'economic_anomaly_widget', 'economic_export_readiness_widget'})
    anomaly_widget = next((item for item in widgets if item.get('widget_id') == 'economic_anomaly_widget'), None)
    export_widget = next((item for item in widgets if item.get('widget_id') == 'economic_export_readiness_widget'), None)
    return EconomicTruthResponse(
        found=True,
        scope_type='client_outcome_anomalies',
        scope_id=order_id,
        tenant_id=str(read_model.get('tenant_id') or ''),
        business_id=str(read_model.get('business_id') or ''),
        truth={
            'anomaly': None if anomaly_widget is None else anomaly_widget.get('payload'),
            'export_readiness': None if export_widget is None else export_widget.get('payload'),
        },
        snapshot=read_model.get('snapshot'),
        widgets=widgets,
    )
