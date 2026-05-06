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

def get_spend_truth(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return EconomicTruthResponse(found=False)
    truth, _recon, _order, _lifecycle, _corrected = payloads
    spend_truth = build_spend_truth_snapshot_from_client_outcome(truth_snapshot=truth)
    spend_fragment = build_spend_truth_fragment(spend_snapshot=spend_truth)
    read_model = handlers.admin_read_service.build_read_model(
        scope_type='spend',
        scope_id=order_id,
        tenant_id=spend_fragment.tenant_id,
        business_id=spend_fragment.business_id,
        truth_payload={'spend': spend_truth},
        truth_fragment=spend_fragment,
        fragments=(),
        extra_widgets=(
            {'widget_id': 'economic_spend_widget', 'kind': 'economic_spend', 'payload': spend_truth},
            {'widget_id': 'economic_spend_owner_widget', 'kind': 'economic_spend_owner', 'payload': spend_truth},
            {'widget_id': 'economic_spend_manifest_widget', 'kind': 'economic_spend_manifest', 'payload': build_spend_manifest_from_client_outcome(truth_snapshot=truth)},
        ),
    )
    return EconomicTruthResponse(found=True, **read_model)


def export_spend_truth(handlers, *, order_id: str, lead_id: str) -> EconomicExportResponse:
    read_model = handlers.get_spend_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicExportResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    return EconomicExportResponse(
        found=True,
        scope_type='spend',
        scope_id=order_id,
        algorithm=str(exported['algorithm']),
        hash=str(exported['hash']),
        verified=verify_client_outcome_truth_export(exported),
        export_ready=bool(read_model.snapshot.get('ready_for_export')),
        payload=exported,
    )


def get_spend_audit(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers.get_spend_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicTruthResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    audit_payload = {
        'algorithm': str(exported['algorithm']),
        'hash': str(exported['hash']),
        'verified': verify_client_outcome_truth_export(exported),
        'domains_with_evidence': ('spend',),
        'spend_fact_ready': int((((read_model.truth or {}).get('spend') or {}).get('spend_total_minor') or 0)) > 0,
    }
    return EconomicTruthResponse(found=True, scope_type='spend_audit', scope_id=order_id, tenant_id=str(read_model.tenant_id), business_id=str(read_model.business_id), truth={'audit_provenance': audit_payload}, snapshot=read_model.snapshot, widgets=read_model.widgets)


def get_spend_manifest(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return EconomicTruthResponse(found=False)
    truth, _recon, _order, _lifecycle, _corrected = payloads
    manifest = build_spend_manifest_from_client_outcome(truth_snapshot=truth)
    return EconomicTruthResponse(
        found=True,
        scope_type='spend_manifest',
        scope_id=order_id,
        tenant_id=str(((manifest.get('payload') or {}).get('tenant_id') or '')),
        business_id=str(((manifest.get('payload') or {}).get('business_id') or '')),
        truth={'spend_manifest': manifest},
        snapshot={'scope_type': 'spend_manifest', 'scope_id': order_id, 'domains': ('spend',), 'ready_for_export': bool((manifest.get('payload') or {}).get('ready_for_export'))},
        widgets=({'widget_id': 'economic_spend_manifest_widget', 'kind': 'economic_spend_manifest', 'payload': manifest},),
    )


def get_spend_source_truth(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return EconomicTruthResponse(found=False)
    truth, _recon, _order, _lifecycle, _corrected = payloads
    fact = build_spend_source_fact_from_client_outcome(truth_snapshot=truth)
    payload = {
        'tenant_id': fact.tenant_id,
        'business_id': fact.business_id,
        'entity_id': fact.entity_id,
        'source_channel': fact.source_channel,
        'source_kind': fact.source_kind,
        'tracking_token': fact.tracking_token,
        'click_id': fact.click_id,
        'session_id': fact.session_id,
        'status': fact.status,
        'issues': fact.issues,
        'evidence_refs': fact.evidence_refs,
        'ready_for_export': fact.ready_for_export,
    }
    return EconomicTruthResponse(
        found=True,
        scope_type='spend_source',
        scope_id=order_id,
        tenant_id=fact.tenant_id,
        business_id=fact.business_id,
        truth={'spend_source': payload},
        snapshot={'scope_type': 'spend_source', 'scope_id': order_id, 'domains': ('spend_source',), 'ready_for_export': fact.ready_for_export},
        widgets=({'widget_id': 'economic_spend_source_widget', 'kind': 'economic_spend_source', 'payload': payload},),
    )


def export_spend_source_truth(handlers, *, order_id: str, lead_id: str) -> EconomicExportResponse:
    read_model = handlers.get_spend_source_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicExportResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    return EconomicExportResponse(
        found=True,
        scope_type='spend_source',
        scope_id=order_id,
        algorithm=str(exported['algorithm']),
        hash=str(exported['hash']),
        verified=verify_client_outcome_truth_export(exported),
        export_ready=bool(read_model.snapshot.get('ready_for_export')),
        payload=exported,
    )


def get_spend_source_audit(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers.get_spend_source_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicTruthResponse(found=False)
    manifest = build_spend_source_manifest_from_client_outcome(truth_snapshot=((read_model.truth or {}).get('spend_source') or {}))
    return EconomicTruthResponse(
        found=True,
        scope_type='spend_source_audit',
        scope_id=order_id,
        tenant_id=str(read_model.tenant_id),
        business_id=str(read_model.business_id),
        truth={'audit_provenance': manifest},
        snapshot=read_model.snapshot,
        widgets=read_model.widgets,
    )


def get_spend_source_manifest(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return EconomicTruthResponse(found=False)
    truth, _recon, _order, _lifecycle, _corrected = payloads
    manifest = build_spend_source_manifest_from_client_outcome(truth_snapshot=truth)
    return EconomicTruthResponse(
        found=True,
        scope_type='spend_source_manifest',
        scope_id=order_id,
        tenant_id=str(((manifest.get('payload') or {}).get('tenant_id') or '')),
        business_id=str(((manifest.get('payload') or {}).get('business_id') or '')),
        truth={'spend_source_manifest': manifest},
        snapshot={'scope_type': 'spend_source_manifest', 'scope_id': order_id, 'domains': ('spend_source',), 'ready_for_export': bool((manifest.get('payload') or {}).get('ready_for_export'))},
        widgets=({'widget_id': 'economic_spend_source_manifest_widget', 'kind': 'economic_spend_source_manifest', 'payload': manifest},),
    )


def get_spend_source_ingress_truth(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    payloads = handlers._build_client_outcome_payloads(order_id=order_id, lead_id=lead_id)
    if payloads is None:
        return EconomicTruthResponse(found=False)
    truth, _recon, _order, _lifecycle, _corrected = payloads
    record = build_spend_source_ingress_record_from_client_outcome(truth_snapshot=truth)
    payload = {
        'tenant_id': record.tenant_id,
        'business_id': record.business_id,
        'entity_id': record.entity_id,
        'source_channel': record.source_channel,
        'source_kind': record.source_kind,
        'tracking_token': record.tracking_token,
        'click_id': record.click_id,
        'session_id': record.session_id,
        'status': record.status,
        'blockers': record.blockers,
        'lifecycle_stages': record.lifecycle_stages,
        'evidence_refs': record.evidence_refs,
        'ready_for_export': record.ready_for_export,
    }
    return EconomicTruthResponse(
        found=True,
        scope_type='spend_source_ingress',
        scope_id=order_id,
        tenant_id=record.tenant_id,
        business_id=record.business_id,
        truth={'spend_source_ingress': payload},
        snapshot={'scope_type': 'spend_source_ingress', 'scope_id': order_id, 'domains': ('spend_source',), 'ready_for_export': record.ready_for_export},
        widgets=({'widget_id': 'economic_spend_source_ingress_widget', 'kind': 'economic_spend_source_ingress', 'payload': payload},),
    )


def export_spend_source_ingress_truth(handlers, *, order_id: str, lead_id: str) -> EconomicExportResponse:
    read_model = handlers.get_spend_source_ingress_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicExportResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    return EconomicExportResponse(
        found=True,
        scope_type='spend_source_ingress',
        scope_id=order_id,
        algorithm=str(exported['algorithm']),
        hash=str(exported['hash']),
        verified=verify_client_outcome_truth_export(exported),
        export_ready=bool(read_model.snapshot.get('ready_for_export')),
        payload=exported,
    )


def get_spend_source_ingress_audit(handlers, *, order_id: str, lead_id: str) -> EconomicTruthResponse:
    read_model = handlers.get_spend_source_ingress_truth(order_id=order_id, lead_id=lead_id)
    if not read_model.found:
        return EconomicTruthResponse(found=False)
    exported = export_client_outcome_truth_snapshot(read_model.truth)
    payload = ((read_model.truth or {}).get('spend_source_ingress') or {})
    audit_payload = {
        'algorithm': str(exported['algorithm']),
        'hash': str(exported['hash']),
        'verified': verify_client_outcome_truth_export(exported),
        'domains_with_evidence': ('spend_source_ingress',) if tuple(payload.get('evidence_refs') or ()) else tuple(),
        'ingress_ready': str(payload.get('status') or '') == 'ready',
        'ready_for_export': bool(payload.get('ready_for_export')),
        'blocker_count': len(tuple(payload.get('blockers') or ())),
    }
    return EconomicTruthResponse(found=True, scope_type='spend_source_ingress_audit', scope_id=order_id, tenant_id=str(read_model.tenant_id), business_id=str(read_model.business_id), truth={'audit_provenance': audit_payload}, snapshot=read_model.snapshot, widgets=read_model.widgets)
