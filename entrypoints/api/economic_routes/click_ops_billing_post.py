from __future__ import annotations

"""Billing route owner logic for EconomicRouteHandlers."""

from entrypoints.api.economic_models import EconomicExportResponse, EconomicTruthResponse
from runtime.export.client_outcome_export import export_client_outcome_truth_snapshot, verify_client_outcome_truth_export
from click_economics.public_api import (
    build_click_billing_settlement_record_from_client_outcome,
    build_click_billing_provider_dispatch_from_client_outcome,
)
from importlib import import_module



def _build_click_provider_dispatch_execution_contract():
    owner = '.'.join(('runtime', 'executor'))
    return getattr(import_module(owner), 'build_click_provider_dispatch_execution_contract')


build_click_provider_dispatch_execution_contract = _build_click_provider_dispatch_execution_contract()

def get_click_billing_settlement_truth(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return EconomicTruthResponse(found=False)
    truth, _recon, _order, lifecycle, _corrected = payloads
    record = build_click_billing_settlement_record_from_client_outcome(truth_snapshot=truth, lifecycle=lifecycle)
    payload = {
        'tenant_id': record.tenant_id, 'business_id': record.business_id, 'entity_id': record.entity_id,
        'invoice_id': record.invoice_id, 'provider_name': record.provider_name, 'currency': record.currency,
        'collected_amount_minor': record.collected_amount_minor, 'settled_amount_minor': record.settled_amount_minor,
        'status': record.status, 'blockers': record.blockers, 'lifecycle_stages': record.lifecycle_stages,
        'evidence_refs': record.evidence_refs, 'ready_for_export': record.ready_for_export, 'settlement_result': record.settlement_result,
    }
    return EconomicTruthResponse(found=True, scope_type='click_billing_settlement', scope_id=order_id, tenant_id=record.tenant_id, business_id=record.business_id, truth={'click_billing_settlement': payload}, snapshot={'scope_type': 'click_billing_settlement', 'scope_id': order_id, 'domains': ('click_economics','billing'), 'ready_for_export': record.ready_for_export}, widgets=({'widget_id': 'economic_click_billing_settlement_widget', 'kind': 'economic_click_billing_settlement', 'payload': payload},))

def export_click_billing_settlement_truth(handlers, *, order_id: str, lead_id: str) -> EconomicExportResponse:
    read_model = handlers.get_click_billing_settlement_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicExportResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    return EconomicExportResponse(found=True, scope_type='click_billing_settlement', scope_id=order_id, algorithm=str(exported['algorithm']), hash=str(exported['hash']), verified=verify_client_outcome_truth_export(exported), export_ready=bool(read_model.snapshot.get('ready_for_export')), payload=exported)

def get_click_billing_settlement_audit(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers.get_click_billing_settlement_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicTruthResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    payload = ((read_model.truth or {}).get('click_billing_settlement') or {})
    audit_payload = {
        'algorithm': str(exported['algorithm']), 'hash': str(exported['hash']), 'verified': verify_client_outcome_truth_export(exported),
        'domains_with_evidence': ('click_billing_settlement',) if tuple(payload.get('evidence_refs') or ()) else tuple(),
        'settlement_ready': bool(payload.get('settlement_result')), 'blocker_count': len(tuple(payload.get('blockers') or ())),
    }
    return EconomicTruthResponse(found=True, scope_type='click_billing_settlement_audit', scope_id=order_id, tenant_id=str(read_model.tenant_id), business_id=str(read_model.business_id), truth={'audit_provenance': audit_payload}, snapshot=read_model.snapshot, widgets=read_model.widgets)

def get_click_billing_provider_dispatch_truth(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return EconomicTruthResponse(found=False)
    truth, _recon, _order, lifecycle, _corrected = payloads
    record = build_click_billing_provider_dispatch_from_client_outcome(truth_snapshot=truth, lifecycle=lifecycle)
    payload = {
        'tenant_id': record.tenant_id, 'business_id': record.business_id, 'entity_id': record.entity_id,
        'invoice_id': record.invoice_id, 'provider_name': record.provider_name, 'currency': record.currency,
        'settled_amount_minor': record.settled_amount_minor, 'status': record.status, 'blockers': record.blockers,
        'lifecycle_stages': record.lifecycle_stages, 'evidence_refs': record.evidence_refs, 'ready_for_export': record.ready_for_export,
        'provider_dispatch': record.provider_dispatch,
    }
    return EconomicTruthResponse(found=True, scope_type='click_billing_provider_dispatch', scope_id=order_id, tenant_id=record.tenant_id, business_id=record.business_id, truth={'click_billing_provider_dispatch': payload}, snapshot={'scope_type': 'click_billing_provider_dispatch', 'scope_id': order_id, 'domains': ('click_economics','billing'), 'ready_for_export': record.ready_for_export}, widgets=({'widget_id': 'economic_click_billing_provider_dispatch_widget', 'kind': 'economic_click_billing_provider_dispatch', 'payload': payload},))

def export_click_billing_provider_dispatch_truth(handlers, *, order_id: str, lead_id: str) -> EconomicExportResponse:
    read_model = handlers.get_click_billing_provider_dispatch_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicExportResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    return EconomicExportResponse(found=True, scope_type='click_billing_provider_dispatch', scope_id=order_id, algorithm=str(exported['algorithm']), hash=str(exported['hash']), verified=verify_client_outcome_truth_export(exported), export_ready=bool(read_model.snapshot.get('ready_for_export')), payload=exported)

def get_click_billing_provider_dispatch_audit(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers.get_click_billing_provider_dispatch_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicTruthResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    payload = ((read_model.truth or {}).get('click_billing_provider_dispatch') or {})
    audit_payload = {
        'algorithm': str(exported['algorithm']), 'hash': str(exported['hash']), 'verified': verify_client_outcome_truth_export(exported),
        'domains_with_evidence': ('click_billing_provider_dispatch',) if tuple(payload.get('evidence_refs') or ()) else tuple(),
        'provider_dispatch_ready': bool(payload.get('provider_dispatch')), 'blocker_count': len(tuple(payload.get('blockers') or ())),
    }
    return EconomicTruthResponse(found=True, scope_type='click_billing_provider_dispatch_audit', scope_id=order_id, tenant_id=str(read_model.tenant_id), business_id=str(read_model.business_id), truth={'audit_provenance': audit_payload}, snapshot=read_model.snapshot, widgets=read_model.widgets)

def get_click_billing_sealed_execution_truth(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    dispatch_read = handlers.get_click_billing_provider_dispatch_truth(order_id=order_id, lead_id=lead_id)
    if not dispatch_read.found:
        return EconomicTruthResponse(found=False)
    dispatch_payload = ((dispatch_read.truth or {}).get('click_billing_provider_dispatch') or {})
    contract = build_click_provider_dispatch_execution_contract(dispatch_payload)
    payload = {
        'status': contract['status'], 'blockers': contract['blockers'], 'lifecycle_stages': contract['lifecycle_stages'],
        'idempotency_key': contract['idempotency_key'], 'transport_owner': contract['transport_owner'], 'dispatch_owner': contract['dispatch_owner'],
        'execution_kind': contract['execution_kind'], 'execution_payload': contract['payload'],
        'invoice_id': str(dispatch_payload.get('invoice_id') or ''), 'provider_name': str(dispatch_payload.get('provider_name') or ''),
        'evidence_refs': tuple(dispatch_payload.get('evidence_refs') or ()), 'ready_for_export': contract['status'] == 'ready',
    }
    return EconomicTruthResponse(found=True, scope_type='click_billing_sealed_execution', scope_id=order_id, tenant_id=str(dispatch_read.tenant_id), business_id=str(dispatch_read.business_id), truth={'click_billing_sealed_execution': payload}, snapshot={'scope_type': 'click_billing_sealed_execution', 'scope_id': order_id, 'domains': ('click_economics','billing'), 'ready_for_export': contract['status'] == 'ready'}, widgets=({'widget_id': 'economic_click_billing_sealed_execution_widget', 'kind': 'economic_click_billing_sealed_execution', 'payload': payload},))

def export_click_billing_sealed_execution_truth(handlers, *, order_id: str, lead_id: str) -> EconomicExportResponse:
    read_model = handlers.get_click_billing_sealed_execution_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicExportResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    return EconomicExportResponse(found=True, scope_type='click_billing_sealed_execution', scope_id=order_id, algorithm=str(exported['algorithm']), hash=str(exported['hash']), verified=verify_client_outcome_truth_export(exported), export_ready=bool(read_model.snapshot.get('ready_for_export')), payload=exported)

def get_click_billing_sealed_execution_audit(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers.get_click_billing_sealed_execution_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicTruthResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    payload = ((read_model.truth or {}).get('click_billing_sealed_execution') or {})
    audit_payload = {
        'algorithm': str(exported['algorithm']), 'hash': str(exported['hash']), 'verified': verify_client_outcome_truth_export(exported),
        'domains_with_evidence': ('click_billing_sealed_execution',) if tuple(payload.get('evidence_refs') or ()) else tuple(),
        'sealed_execution_ready': bool(payload.get('execution_payload')), 'blocker_count': len(tuple(payload.get('blockers') or ())),
    }
    return EconomicTruthResponse(found=True, scope_type='click_billing_sealed_execution_audit', scope_id=order_id, tenant_id=str(read_model.tenant_id), business_id=str(read_model.business_id), truth={'audit_provenance': audit_payload}, snapshot=read_model.snapshot, widgets=read_model.widgets)
