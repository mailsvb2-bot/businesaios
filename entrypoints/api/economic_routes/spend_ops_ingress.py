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

def get_spend_ingress_envelope_truth(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return EconomicTruthResponse(found=False)
    truth, _recon, _order, _lifecycle, _corrected = payloads
    envelope = build_spend_ingress_envelope_from_client_outcome(truth_snapshot=truth)
    payload = {
        'tenant_id': envelope.tenant_id,
        'business_id': envelope.business_id,
        'entity_id': envelope.entity_id,
        'amount_minor': envelope.amount_minor,
        'currency': envelope.currency,
        'source_channel': envelope.source_channel,
        'source_kind': envelope.source_kind,
        'tracking_token': envelope.tracking_token,
        'click_id': envelope.click_id,
        'session_id': envelope.session_id,
        'status': envelope.status,
        'blockers': envelope.blockers,
        'lifecycle_stages': envelope.lifecycle_stages,
        'evidence_refs': envelope.evidence_refs,
        'ready_for_export': envelope.ready_for_export,
    }
    return EconomicTruthResponse(found=True, scope_type='spend_ingress_envelope', scope_id=order_id, tenant_id=envelope.tenant_id, business_id=envelope.business_id, truth={'spend_ingress_envelope': payload}, snapshot={'scope_type': 'spend_ingress_envelope', 'scope_id': order_id, 'domains': ('spend','spend_source'), 'ready_for_export': envelope.ready_for_export}, widgets=({'widget_id': 'economic_spend_ingress_envelope_widget', 'kind': 'economic_spend_ingress_envelope', 'payload': payload},))


def export_spend_ingress_envelope_truth(handlers, *, order_id: str, lead_id: str) -> EconomicExportResponse:
    read_model = handlers.get_spend_ingress_envelope_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicExportResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    return EconomicExportResponse(found=True, scope_type='spend_ingress_envelope', scope_id=order_id, algorithm=str(exported['algorithm']), hash=str(exported['hash']), verified=verify_client_outcome_truth_export(exported), export_ready=bool(read_model.snapshot.get('ready_for_export')), payload=exported)


def get_spend_ingress_envelope_audit(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers.get_spend_ingress_envelope_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicTruthResponse(found=False)
    payload = ((read_model.truth or {}).get('spend_ingress_envelope') or {})
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    audit_payload = {
        'algorithm': str(exported['algorithm']),
        'hash': str(exported['hash']),
        'verified': verify_client_outcome_truth_export(exported),
        'payload': payload,
        'domains_with_evidence': ('spend_ingress_envelope',) if tuple(payload.get('evidence_refs') or ()) else tuple(),
        'evidence_ref_count': len(tuple(payload.get('evidence_refs') or ())),
    }
    return EconomicTruthResponse(found=True, scope_type='spend_ingress_envelope_audit', scope_id=order_id, tenant_id=str(read_model.tenant_id), business_id=str(read_model.business_id), truth={'audit_provenance': audit_payload}, snapshot=read_model.snapshot, widgets=read_model.widgets)


def get_spend_external_ingress_truth(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return EconomicTruthResponse(found=False)
    truth, _recon, _order, _lifecycle, _corrected = payloads
    batch = build_spend_external_ingress_batch_from_client_outcome(truth_snapshot=truth)
    payload = {
        'tenant_id': batch.tenant_id, 'business_id': batch.business_id, 'entity_id': batch.entity_id, 'batch_id': batch.batch_id,
        'amount_minor': batch.amount_minor, 'currency': batch.currency, 'source_channel': batch.source_channel, 'source_kind': batch.source_kind,
        'status': batch.status, 'blockers': batch.blockers, 'lifecycle_stages': batch.lifecycle_stages, 'evidence_refs': batch.evidence_refs,
        'ready_for_export': batch.ready_for_export, 'batch_payload': batch.batch_payload,
    }
    return EconomicTruthResponse(found=True, scope_type='spend_external_ingress', scope_id=order_id, tenant_id=batch.tenant_id, business_id=batch.business_id, truth={'spend_external_ingress': payload}, snapshot={'scope_type': 'spend_external_ingress', 'scope_id': order_id, 'domains': ('spend','spend_source'), 'ready_for_export': batch.ready_for_export}, widgets=({'widget_id': 'economic_spend_external_ingress_widget', 'kind': 'economic_spend_external_ingress', 'payload': payload},))


def export_spend_external_ingress_truth(handlers, *, order_id: str, lead_id: str) -> EconomicExportResponse:
    read_model = handlers.get_spend_external_ingress_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicExportResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    return EconomicExportResponse(found=True, scope_type='spend_external_ingress', scope_id=order_id, algorithm=str(exported['algorithm']), hash=str(exported['hash']), verified=verify_client_outcome_truth_export(exported), export_ready=bool(read_model.snapshot.get('ready_for_export')), payload=exported)


def get_spend_external_ingress_audit(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers.get_spend_external_ingress_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicTruthResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    payload = ((read_model.truth or {}).get('spend_external_ingress') or {})
    audit_payload = {
        'algorithm': str(exported['algorithm']), 'hash': str(exported['hash']), 'verified': verify_client_outcome_truth_export(exported),
        'domains_with_evidence': ('spend_external_ingress',) if tuple(payload.get('evidence_refs') or ()) else tuple(),
        'external_batch_ready': bool(payload.get('batch_payload')), 'blocker_count': len(tuple(payload.get('blockers') or ())),
    }
    return EconomicTruthResponse(found=True, scope_type='spend_external_ingress_audit', scope_id=order_id, tenant_id=str(read_model.tenant_id), business_id=str(read_model.business_id), truth={'audit_provenance': audit_payload}, snapshot=read_model.snapshot, widgets=read_model.widgets)


def get_spend_external_runtime_request_truth(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return EconomicTruthResponse(found=False)
    truth, _recon, _order, _lifecycle, _corrected = payloads
    record = build_spend_external_ingress_runtime_request_from_client_outcome(truth_snapshot=truth)
    payload = {
        'tenant_id': record.tenant_id, 'business_id': record.business_id, 'entity_id': record.entity_id, 'batch_id': record.batch_id,
        'amount_minor': record.amount_minor, 'currency': record.currency, 'status': record.status, 'blockers': record.blockers,
        'lifecycle_stages': record.lifecycle_stages, 'evidence_refs': record.evidence_refs, 'ready_for_export': record.ready_for_export,
        'runtime_request': record.runtime_request,
    }
    return EconomicTruthResponse(found=True, scope_type='spend_external_runtime_request', scope_id=order_id, tenant_id=record.tenant_id, business_id=record.business_id, truth={'spend_external_runtime_request': payload}, snapshot={'scope_type': 'spend_external_runtime_request', 'scope_id': order_id, 'domains': ('spend','spend_source'), 'ready_for_export': record.ready_for_export}, widgets=({'widget_id': 'economic_spend_external_runtime_request_widget', 'kind': 'economic_spend_external_runtime_request', 'payload': payload},))


def export_spend_external_runtime_request_truth(handlers, *, order_id: str, lead_id: str) -> EconomicExportResponse:
    read_model = handlers.get_spend_external_runtime_request_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicExportResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    return EconomicExportResponse(found=True, scope_type='spend_external_runtime_request', scope_id=order_id, algorithm=str(exported['algorithm']), hash=str(exported['hash']), verified=verify_client_outcome_truth_export(exported), export_ready=bool(read_model.snapshot.get('ready_for_export')), payload=exported)


def get_spend_external_runtime_request_audit(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers.get_spend_external_runtime_request_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicTruthResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    payload = ((read_model.truth or {}).get('spend_external_runtime_request') or {})
    audit_payload = {
        'algorithm': str(exported['algorithm']), 'hash': str(exported['hash']), 'verified': verify_client_outcome_truth_export(exported),
        'domains_with_evidence': ('spend_external_runtime_request',) if tuple(payload.get('evidence_refs') or ()) else tuple(),
        'runtime_request_ready': bool(payload.get('runtime_request')), 'blocker_count': len(tuple(payload.get('blockers') or ())),
    }
    return EconomicTruthResponse(found=True, scope_type='spend_external_runtime_request_audit', scope_id=order_id, tenant_id=str(read_model.tenant_id), business_id=str(read_model.business_id), truth={'audit_provenance': audit_payload}, snapshot=read_model.snapshot, widgets=read_model.widgets)


def get_spend_external_sealed_execution_truth(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    runtime_read = handlers.get_spend_external_runtime_request_truth(order_id=order_id, lead_id=lead_id)
    if not runtime_read.found:
        return EconomicTruthResponse(found=False)
    runtime_payload = ((runtime_read.truth or {}).get('spend_external_runtime_request') or {})
    contract = build_spend_runtime_execution_contract(runtime_payload)
    payload = {
        'status': contract['status'], 'blockers': contract['blockers'], 'lifecycle_stages': contract['lifecycle_stages'],
        'idempotency_key': contract['idempotency_key'], 'transport_owner': contract['transport_owner'], 'dispatch_owner': contract['dispatch_owner'],
        'execution_kind': contract['execution_kind'], 'execution_payload': contract['payload'],
        'batch_id': str(runtime_payload.get('batch_id') or ''), 'evidence_refs': tuple(runtime_payload.get('evidence_refs') or ()),
        'ready_for_export': contract['status'] == 'ready',
    }
    return EconomicTruthResponse(found=True, scope_type='spend_external_sealed_execution', scope_id=order_id, tenant_id=str(runtime_read.tenant_id), business_id=str(runtime_read.business_id), truth={'spend_external_sealed_execution': payload}, snapshot={'scope_type': 'spend_external_sealed_execution', 'scope_id': order_id, 'domains': ('spend','spend_source'), 'ready_for_export': contract['status'] == 'ready'}, widgets=({'widget_id': 'economic_spend_external_sealed_execution_widget', 'kind': 'economic_spend_external_sealed_execution', 'payload': payload},))


def export_spend_external_sealed_execution_truth(handlers, *, order_id: str, lead_id: str) -> EconomicExportResponse:
    read_model = handlers.get_spend_external_sealed_execution_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicExportResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    return EconomicExportResponse(found=True, scope_type='spend_external_sealed_execution', scope_id=order_id, algorithm=str(exported['algorithm']), hash=str(exported['hash']), verified=verify_client_outcome_truth_export(exported), export_ready=bool(read_model.snapshot.get('ready_for_export')), payload=exported)


def get_spend_external_sealed_execution_audit(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers.get_spend_external_sealed_execution_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicTruthResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    payload = ((read_model.truth or {}).get('spend_external_sealed_execution') or {})
    audit_payload = {
        'algorithm': str(exported['algorithm']), 'hash': str(exported['hash']), 'verified': verify_client_outcome_truth_export(exported),
        'domains_with_evidence': ('spend_external_sealed_execution',) if tuple(payload.get('evidence_refs') or ()) else tuple(),
        'sealed_execution_ready': bool(payload.get('execution_payload')), 'blocker_count': len(tuple(payload.get('blockers') or ())),
    }
    return EconomicTruthResponse(found=True, scope_type='spend_external_sealed_execution_audit', scope_id=order_id, tenant_id=str(read_model.tenant_id), business_id=str(read_model.business_id), truth={'audit_provenance': audit_payload}, snapshot=read_model.snapshot, widgets=read_model.widgets)
