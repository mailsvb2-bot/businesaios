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

def _build_business_truth(handlers, *, order_id: str, lead_id: str) -> dict[str, Any] | None:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return None
    truth, recon, _order, lifecycle, corrected_economics = payloads
    client_outcome_fragment = build_client_outcome_truth_fragment(truth_snapshot=truth)
    billing_truth = build_billing_truth_snapshot_from_client_outcome(truth_snapshot=truth, corrected_economics=corrected_economics)
    billing_fragment = build_billing_truth_fragment(billing_snapshot=billing_truth)
    acquisition_truth = build_acquisition_truth_snapshot_from_client_outcome(truth_snapshot=truth)
    acquisition_fragment = build_acquisition_truth_fragment(acquisition_snapshot=acquisition_truth)
    attribution_truth = build_attribution_truth_snapshot_from_client_outcome(truth_snapshot=truth, lifecycle=lifecycle)
    attribution_fragment = build_attribution_truth_fragment(attribution_snapshot=attribution_truth)
    click_truth = build_click_economics_truth_snapshot_from_client_outcome(truth_snapshot=truth, lifecycle=lifecycle)
    click_fragment = build_click_economics_truth_fragment(click_snapshot=click_truth)
    spend_truth = build_spend_truth_snapshot_from_client_outcome(truth_snapshot=truth)
    spend_fragment = build_spend_truth_fragment(spend_snapshot=spend_truth)
    anomaly_truth = build_anomaly_truth_snapshot(reconciliation=recon, billing_snapshot=billing_truth, attribution_snapshot=attribution_truth)
    anomaly_fragment = build_anomaly_truth_fragment(anomaly_snapshot=anomaly_truth)
    export_readiness_truth = build_export_readiness_snapshot(reconciliation=recon, anomaly_snapshot=anomaly_truth)
    export_readiness_fragment = build_export_readiness_fragment(export_readiness_snapshot=export_readiness_truth)
    audit_truth = build_audit_provenance_snapshot(
        truth_payload=truth,
        fragments=(client_outcome_fragment, billing_fragment, acquisition_fragment, attribution_fragment, click_fragment, spend_fragment, anomaly_fragment, export_readiness_fragment),
    )
    audit_fragment = build_audit_provenance_fragment(audit_snapshot=audit_truth)
    unified_truth = {
        'business_id': client_outcome_fragment.business_id,
        'tenant_id': client_outcome_fragment.tenant_id,
        'scope_order_id': order_id,
        'domains': {
            'client_outcome': truth,
            'billing': billing_truth,
            'acquisition': acquisition_truth,
            'attribution': attribution_truth,
            'click_economics': click_truth,
            'spend': spend_truth,
            'anomaly': anomaly_truth,
            'export_readiness': export_readiness_truth,
            'audit_provenance': audit_truth,
        },
    }
    return handlers.admin_read_service.build_read_model(
        scope_type='business',
        scope_id=client_outcome_fragment.business_id,
        tenant_id=client_outcome_fragment.tenant_id,
        business_id=client_outcome_fragment.business_id,
        truth_payload=unified_truth,
        truth_fragment=client_outcome_fragment,
        fragments=(billing_fragment, acquisition_fragment, attribution_fragment, click_fragment, spend_fragment, anomaly_fragment, export_readiness_fragment, audit_fragment),
        extra_widgets=(
            {
                'widget_id': 'economic_domain_summary',
                'kind': 'domain_summary',
                'payload': {
                    'domains': ('client_outcome', 'billing', 'acquisition', 'attribution', 'click_economics', 'spend', 'anomaly', 'export_readiness', 'audit_provenance'),
                    'billing_status': billing_truth.get('billing_status'),
                    'invoice_id': billing_truth.get('invoice_id'),
                    'refund_total_minor': billing_truth.get('refund_total_minor'),
                },
            },
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

def get_business_truth(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers._build_business_truth(order_id=order_id, lead_id=lead_id)
    if read_model is None:
        return EconomicTruthResponse(found=False)
    return EconomicTruthResponse(found=True, **read_model)

def export_business_truth(handlers, *, order_id: str, lead_id: str) -> EconomicExportResponse:
    read_model = handlers._build_business_truth(order_id=order_id, lead_id=lead_id)
    if read_model is None:
        return EconomicExportResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model['truth'])
    return EconomicExportResponse(
        found=True,
        scope_type='business',
        scope_id=str(read_model['scope_id']),
        algorithm=str(exported['algorithm']),
        hash=str(exported['hash']),
        verified=verify_client_outcome_truth_export(exported),
        export_ready=bool(read_model['snapshot'].get('ready_for_export')),
        payload=exported,
    )

def get_business_audit(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers._build_business_truth(order_id=order_id, lead_id=lead_id)
    if read_model is None:
        return EconomicTruthResponse(found=False)
    widgets = tuple(item for item in tuple(read_model.get('widgets') or ()) if item.get('widget_id') in {'economic_audit_provenance_widget', 'economic_export_readiness_widget'})
    audit_widget = next((item for item in widgets if item.get('widget_id') == 'economic_audit_provenance_widget'), None)
    export_widget = next((item for item in widgets if item.get('widget_id') == 'economic_export_readiness_widget'), None)
    return EconomicTruthResponse(
        found=True,
        scope_type='business_audit',
        scope_id=str(read_model.get('scope_id') or ''),
        tenant_id=str(read_model.get('tenant_id') or ''),
        business_id=str(read_model.get('business_id') or ''),
        truth={
            'audit_provenance': None if audit_widget is None else audit_widget.get('payload'),
            'export_readiness': None if export_widget is None else export_widget.get('payload'),
        },
        snapshot=read_model.get('snapshot'),
        widgets=widgets,
    )

def get_business_anomalies(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers._build_business_truth(order_id=order_id, lead_id=lead_id)
    if read_model is None:
        return EconomicTruthResponse(found=False)
    widgets = tuple(item for item in tuple(read_model.get('widgets') or ()) if item.get('widget_id') in {'economic_anomaly_widget', 'economic_export_readiness_widget'})
    anomaly_widget = next((item for item in widgets if item.get('widget_id') == 'economic_anomaly_widget'), None)
    export_widget = next((item for item in widgets if item.get('widget_id') == 'economic_export_readiness_widget'), None)
    return EconomicTruthResponse(
        found=True,
        scope_type='business_anomalies',
        scope_id=str(read_model.get('scope_id') or ''),
        tenant_id=str(read_model.get('tenant_id') or ''),
        business_id=str(read_model.get('business_id') or ''),
        truth={
            'anomaly': None if anomaly_widget is None else anomaly_widget.get('payload'),
            'export_readiness': None if export_widget is None else export_widget.get('payload'),
        },
        snapshot=read_model.get('snapshot'),
        widgets=widgets,
    )

def get_business_cross_domain_reconciliation(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return EconomicTruthResponse(found=False)
    truth, _recon, _order, lifecycle, corrected_economics = payloads
    billing_truth = build_billing_truth_snapshot_from_client_outcome(truth_snapshot=truth, corrected_economics=corrected_economics)
    click_truth = build_click_economics_truth_snapshot_from_client_outcome(truth_snapshot=truth, lifecycle=lifecycle)
    spend_truth = build_spend_truth_snapshot_from_client_outcome(truth_snapshot=truth)
    spend_source = build_spend_source_fact_from_client_outcome(truth_snapshot=truth)
    spend_external = build_spend_external_ingress_batch_from_client_outcome(truth_snapshot=truth)
    spend_runtime_request = (handlers.get_spend_external_runtime_request_truth(order_id=order_id, lead_id=lead_id).truth or {}).get('spend_external_runtime_request', {})
    click_collection = (handlers.get_click_billing_collection_truth(order_id=order_id, lead_id=lead_id).truth or {}).get('click_billing_collection', {})
    click_execution = (handlers.get_click_billing_execution_truth(order_id=order_id, lead_id=lead_id).truth or {}).get('click_billing_execution', {})
    click_settlement = build_click_billing_settlement_record_from_client_outcome(truth_snapshot=truth, lifecycle=lifecycle)
    click_provider_dispatch = (handlers.get_click_billing_provider_dispatch_truth(order_id=order_id, lead_id=lead_id).truth or {}).get('click_billing_provider_dispatch', {})
    click_sealed_execution = (handlers.get_click_billing_sealed_execution_truth(order_id=order_id, lead_id=lead_id).truth or {}).get('click_billing_sealed_execution', {})
    spend_sealed_execution = (handlers.get_spend_external_sealed_execution_truth(order_id=order_id, lead_id=lead_id).truth or {}).get('spend_external_sealed_execution', {})
    payload = build_cross_domain_reconciliation_snapshot(
        client_outcome_truth=truth,
        billing_truth=billing_truth,
        click_truth=click_truth,
        spend_truth=spend_truth,
        spend_source={
            'status': spend_source.status,
            'tracking_token': spend_source.tracking_token,
            'click_id': spend_source.click_id,
            'session_id': spend_source.session_id,
            'external_batch_status': spend_external.status,
        },
        click_collection={
            'collection_preview': click_collection.get('collection_preview'),
            'execution_result': click_execution.get('execution_result'),
            'settlement_result': click_settlement.settlement_result,
        },
        click_provider_dispatch={
            'provider_dispatch': click_provider_dispatch.get('provider_dispatch'),
        },
        spend_runtime_request={
            'runtime_request': spend_runtime_request.get('runtime_request'),
        },
        click_sealed_execution={
            'status': click_sealed_execution.get('status'),
            'execution_payload': click_sealed_execution.get('execution_payload'),
        },
        spend_sealed_execution={
            'status': spend_sealed_execution.get('status'),
            'execution_payload': spend_sealed_execution.get('execution_payload'),
        },
    )
    return EconomicTruthResponse(found=True, scope_type='business_cross_domain_reconciliation', scope_id=order_id, tenant_id=str(truth.get('tenant_id') or ''), business_id=str(truth.get('business_id') or ''), truth={'cross_domain_reconciliation': payload}, snapshot={'scope_type': 'business_cross_domain_reconciliation', 'scope_id': order_id, 'domains': ('client_outcome','billing','click_economics','spend'), 'ready_for_export': bool(payload.get('consistent'))}, widgets=({'widget_id': 'economic_cross_domain_reconciliation_widget', 'kind': 'economic_cross_domain_reconciliation', 'payload': payload},))
