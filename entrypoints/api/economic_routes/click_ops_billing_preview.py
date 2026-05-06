from __future__ import annotations

"""Billing route owner logic for EconomicRouteHandlers."""

from entrypoints.api.economic_models import EconomicExportResponse, EconomicTruthResponse
from runtime.export.client_outcome_export import export_client_outcome_truth_snapshot, verify_client_outcome_truth_export
from click_economics.public_api import (
    build_click_billing_handoff_record_from_client_outcome,
    build_click_billing_invoice_preview_from_client_outcome,
    build_click_billing_collection_preview_from_client_outcome,
    build_click_billing_execution_record_from_client_outcome,
)


def get_click_billing_invoice_truth(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return EconomicTruthResponse(found=False)
    truth, _recon, _order, lifecycle, _corrected = payloads
    preview = build_click_billing_invoice_preview_from_client_outcome(truth_snapshot=truth, lifecycle=lifecycle)
    payload = {
        'tenant_id': preview.tenant_id,
        'business_id': preview.business_id,
        'entity_id': preview.entity_id,
        'invoice_id': preview.invoice_id,
        'currency': preview.currency,
        'total_minor': preview.total_minor,
        'status': preview.status,
        'blockers': preview.blockers,
        'lifecycle_stages': preview.lifecycle_stages,
        'evidence_refs': preview.evidence_refs,
        'ready_for_export': preview.ready_for_export,
        'invoice_preview': preview.invoice_preview,
    }
    return EconomicTruthResponse(
        found=True,
        scope_type='click_billing_invoice',
        scope_id=order_id,
        tenant_id=preview.tenant_id,
        business_id=preview.business_id,
        truth={'click_billing_invoice': payload},
        snapshot={'scope_type': 'click_billing_invoice', 'scope_id': order_id, 'domains': ('click_economics', 'billing'), 'ready_for_export': preview.ready_for_export},
        widgets=({'widget_id': 'economic_click_billing_invoice_widget', 'kind': 'economic_click_billing_invoice', 'payload': payload},),
    )

def export_click_billing_invoice_truth(handlers, *, order_id: str, lead_id: str) -> EconomicExportResponse:
    read_model = handlers.get_click_billing_invoice_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicExportResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    return EconomicExportResponse(
        found=True,
        scope_type='click_billing_invoice',
        scope_id=order_id,
        algorithm=str(exported['algorithm']),
        hash=str(exported['hash']),
        verified=verify_client_outcome_truth_export(exported),
        export_ready=bool(read_model.snapshot.get('ready_for_export')),
        payload=exported,
    )

def get_click_billing_invoice_audit(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers.get_click_billing_invoice_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicTruthResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    payload = ((read_model.truth or {}).get('click_billing_invoice') or {})
    audit_payload = {
        'algorithm': str(exported['algorithm']),
        'hash': str(exported['hash']),
        'verified': verify_client_outcome_truth_export(exported),
        'domains_with_evidence': ('click_billing_invoice',) if tuple(payload.get('evidence_refs') or ()) else tuple(),
        'invoice_preview_ready': bool(payload.get('invoice_preview')),
        'blocker_count': len(tuple(payload.get('blockers') or ())),
    }
    return EconomicTruthResponse(found=True, scope_type='click_billing_invoice_audit', scope_id=order_id, tenant_id=str(read_model.tenant_id), business_id=str(read_model.business_id), truth={'audit_provenance': audit_payload}, snapshot=read_model.snapshot, widgets=read_model.widgets)

def get_click_billing_collection_truth(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return EconomicTruthResponse(found=False)
    truth, _recon, _order, lifecycle, _corrected = payloads
    preview = build_click_billing_collection_preview_from_client_outcome(truth_snapshot=truth, lifecycle=lifecycle)
    payload = {
        'tenant_id': preview.tenant_id,
        'business_id': preview.business_id,
        'entity_id': preview.entity_id,
        'invoice_id': preview.invoice_id,
        'provider_name': preview.provider_name,
        'currency': preview.currency,
        'total_minor': preview.total_minor,
        'collectible_amount_minor': preview.collectible_amount_minor,
        'status': preview.status,
        'blockers': preview.blockers,
        'lifecycle_stages': preview.lifecycle_stages,
        'evidence_refs': preview.evidence_refs,
        'ready_for_export': preview.ready_for_export,
        'collection_preview': preview.collection_preview,
    }
    return EconomicTruthResponse(
        found=True,
        scope_type='click_billing_collection',
        scope_id=order_id,
        tenant_id=preview.tenant_id,
        business_id=preview.business_id,
        truth={'click_billing_collection': payload},
        snapshot={'scope_type': 'click_billing_collection', 'scope_id': order_id, 'domains': ('click_economics', 'billing'), 'ready_for_export': preview.ready_for_export},
        widgets=({'widget_id': 'economic_click_billing_collection_widget', 'kind': 'economic_click_billing_collection', 'payload': payload},),
    )

def export_click_billing_collection_truth(handlers, *, order_id: str, lead_id: str) -> EconomicExportResponse:
    read_model = handlers.get_click_billing_collection_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicExportResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    return EconomicExportResponse(found=True, scope_type='click_billing_collection', scope_id=order_id, algorithm=str(exported['algorithm']), hash=str(exported['hash']), verified=verify_client_outcome_truth_export(exported), export_ready=bool(read_model.snapshot.get('ready_for_export')), payload=exported)

def get_click_billing_collection_audit(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers.get_click_billing_collection_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicTruthResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    payload = ((read_model.truth or {}).get('click_billing_collection') or {})
    audit_payload = {
        'algorithm': str(exported['algorithm']),
        'hash': str(exported['hash']),
        'verified': verify_client_outcome_truth_export(exported),
        'domains_with_evidence': ('click_billing_collection',) if tuple(payload.get('evidence_refs') or ()) else tuple(),
        'collection_preview_ready': bool(payload.get('collection_preview')),
        'provider_name': str(payload.get('provider_name') or ''),
    }
    return EconomicTruthResponse(found=True, scope_type='click_billing_collection_audit', scope_id=order_id, tenant_id=str(read_model.tenant_id), business_id=str(read_model.business_id), truth={'audit_provenance': audit_payload}, snapshot=read_model.snapshot, widgets=read_model.widgets)

def get_click_billing_execution_truth(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return EconomicTruthResponse(found=False)
    truth, _recon, _order, lifecycle, _corrected = payloads
    record = build_click_billing_execution_record_from_client_outcome(truth_snapshot=truth, lifecycle=lifecycle)
    payload = {
        'tenant_id': record.tenant_id,
        'business_id': record.business_id,
        'entity_id': record.entity_id,
        'invoice_id': record.invoice_id,
        'provider_name': record.provider_name,
        'currency': record.currency,
        'total_minor': record.total_minor,
        'collected_amount_minor': record.collected_amount_minor,
        'status': record.status,
        'blockers': record.blockers,
        'lifecycle_stages': record.lifecycle_stages,
        'evidence_refs': record.evidence_refs,
        'ready_for_export': record.ready_for_export,
        'execution_result': record.execution_result,
    }
    return EconomicTruthResponse(found=True, scope_type='click_billing_execution', scope_id=order_id, tenant_id=record.tenant_id, business_id=record.business_id, truth={'click_billing_execution': payload}, snapshot={'scope_type': 'click_billing_execution', 'scope_id': order_id, 'domains': ('click_economics','billing'), 'ready_for_export': record.ready_for_export}, widgets=({'widget_id': 'economic_click_billing_execution_widget', 'kind': 'economic_click_billing_execution', 'payload': payload},))

def export_click_billing_execution_truth(handlers, *, order_id: str, lead_id: str) -> EconomicExportResponse:
    read_model = handlers.get_click_billing_execution_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicExportResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    return EconomicExportResponse(found=True, scope_type='click_billing_execution', scope_id=order_id, algorithm=str(exported['algorithm']), hash=str(exported['hash']), verified=verify_client_outcome_truth_export(exported), export_ready=bool(read_model.snapshot.get('ready_for_export')), payload=exported)

def get_click_billing_execution_audit(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers.get_click_billing_execution_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicTruthResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    payload = ((read_model.truth or {}).get('click_billing_execution') or {})
    audit_payload = {
        'algorithm': str(exported['algorithm']),
        'hash': str(exported['hash']),
        'verified': verify_client_outcome_truth_export(exported),
        'domains_with_evidence': ('click_billing_execution',) if tuple(payload.get('evidence_refs') or ()) else tuple(),
        'execution_ready': str(payload.get('status') or '') == 'executed',
        'provider_name': str(payload.get('provider_name') or ''),
        'blocker_count': len(tuple(payload.get('blockers') or ())),
    }
    return EconomicTruthResponse(found=True, scope_type='click_billing_execution_audit', scope_id=order_id, tenant_id=str(read_model.tenant_id), business_id=str(read_model.business_id), truth={'audit_provenance': audit_payload}, snapshot=read_model.snapshot, widgets=read_model.widgets)

def get_click_billing_lifecycle(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return EconomicTruthResponse(found=False)
    truth, _recon, _order, lifecycle, _corrected = payloads
    record = build_click_billing_handoff_record_from_client_outcome(truth_snapshot=truth, lifecycle=lifecycle)
    payload = {
        'tenant_id': record.tenant_id,
        'business_id': record.business_id,
        'entity_id': record.entity_id,
        'status': record.status,
        'blockers': record.blockers,
        'lifecycle_stages': record.lifecycle_stages,
        'ready_for_export': record.ready_for_export,
        'evidence_refs': record.evidence_refs,
        'handoff_contract': record.handoff_contract,
    }
    return EconomicTruthResponse(
        found=True,
        scope_type='click_billing_lifecycle',
        scope_id=order_id,
        tenant_id=record.tenant_id,
        business_id=record.business_id,
        truth={'click_billing_lifecycle': payload},
        snapshot={'scope_type': 'click_billing_lifecycle', 'scope_id': order_id, 'domains': ('click_economics',), 'ready_for_export': record.ready_for_export},
        widgets=({'widget_id': 'economic_click_billing_lifecycle_widget', 'kind': 'economic_click_billing_lifecycle', 'payload': payload},),
    )

def export_click_billing_lifecycle(handlers, *, order_id: str, lead_id: str) -> EconomicExportResponse:
    read_model = handlers.get_click_billing_lifecycle(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicExportResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    return EconomicExportResponse(
        found=True,
        scope_type='click_billing_lifecycle',
        scope_id=order_id,
        algorithm=str(exported['algorithm']),
        hash=str(exported['hash']),
        verified=verify_client_outcome_truth_export(exported),
        export_ready=bool(read_model.snapshot.get('ready_for_export')),
        payload=exported,
    )

def get_click_billing_lifecycle_audit(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers.get_click_billing_lifecycle(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicTruthResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    payload = ((read_model.truth or {}).get('click_billing_lifecycle') or {})
    audit_payload = {
        'algorithm': str(exported['algorithm']),
        'hash': str(exported['hash']),
        'verified': verify_client_outcome_truth_export(exported),
        'domains_with_evidence': ('click_billing_lifecycle',) if tuple(payload.get('evidence_refs') or ()) else tuple(),
        'handoff_ready': bool(payload.get('handoff_contract')),
        'blocker_count': len(tuple(payload.get('blockers') or ())),
    }
    return EconomicTruthResponse(found=True, scope_type='click_billing_lifecycle_audit', scope_id=order_id, tenant_id=str(read_model.tenant_id), business_id=str(read_model.business_id), truth={'audit_provenance': audit_payload}, snapshot=read_model.snapshot, widgets=read_model.widgets)
