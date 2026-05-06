from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .contracts import SpendExternalIngressBatch, SpendExternalIngressRuntimeRequest, SpendFact, SpendIngressEnvelope, SpendSourceFact, SpendSourceIngressRecord

CANON_SPEND_PUBLIC_API = True


def build_spend_fact_from_client_outcome(*, truth_snapshot: Mapping[str, Any]) -> SpendFact:
    truth = dict(truth_snapshot)
    try:
        acquisition_cost = float(truth.get('acquisition_cost') or 0.0)
    except (TypeError, ValueError):
        acquisition_cost = 0.0
    try:
        cac = float(truth.get('cac') or 0.0)
    except (TypeError, ValueError):
        cac = 0.0
    amount_minor = int(round(acquisition_cost * 100))
    unit_cost_minor = int(round(cac * 100)) if cac > 0 else None
    source_channel = str(truth.get('source_channel') or '').strip()
    refs = tuple(ref for ref in (source_channel, str(truth.get('tracking_token') or '').strip()) if ref)
    status = 'captured' if amount_minor > 0 else 'missing'
    issues = tuple(() if amount_minor > 0 else ('missing_spend_fact',))
    return SpendFact(
        tenant_id=str(truth.get('tenant_id') or ''),
        business_id=str(truth.get('business_id') or ''),
        entity_id=str(truth.get('order_id') or ''),
        amount_minor=amount_minor,
        unit_cost_minor=unit_cost_minor,
        source_channel=source_channel,
        status=status,
        issues=issues,
        evidence_refs=refs,
        ready_for_export=bool(truth.get('reconciliation_consistent')) and amount_minor > 0,
    )



def build_spend_export_payload_from_client_outcome(*, truth_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    fact = build_spend_fact_from_client_outcome(truth_snapshot=truth_snapshot)
    return {
        'tenant_id': fact.tenant_id,
        'business_id': fact.business_id,
        'entity_id': fact.entity_id,
        'amount_minor': fact.amount_minor,
        'unit_cost_minor': fact.unit_cost_minor,
        'source_channel': fact.source_channel,
        'status': fact.status,
        'issues': fact.issues,
        'evidence_refs': fact.evidence_refs,
        'ready_for_export': fact.ready_for_export,
    }



def build_spend_manifest_from_client_outcome(*, truth_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    payload = build_spend_export_payload_from_client_outcome(truth_snapshot=truth_snapshot)
    normalized = dict(payload)
    raw = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    return {
        'algorithm': 'sha256',
        'hash': digest,
        'payload': normalized,
        'verified': True,
        'domains_with_evidence': ('spend',),
        'evidence_ref_count': len(tuple(normalized.get('evidence_refs') or ())),
    }



def build_spend_source_fact_from_client_outcome(*, truth_snapshot: Mapping[str, Any]) -> SpendSourceFact:
    truth = dict(truth_snapshot)
    metadata = dict(truth.get('metadata') or {}) if isinstance(truth.get('metadata'), Mapping) else {}
    source_channel = str(truth.get('source_channel') or metadata.get('source_channel') or '').strip()
    tracking_token = str(truth.get('tracking_token') or metadata.get('tracking_token') or '').strip()
    click_id = str(truth.get('click_id') or metadata.get('click_id') or '').strip()
    session_id = str(truth.get('session_id') or metadata.get('session_id') or '').strip()
    if source_channel.lower() in {'ads', 'paid_search', 'paid_social', 'ppc', 'cpc'}:
        source_kind = 'paid'
    elif source_channel:
        source_kind = 'owned_or_organic'
    else:
        source_kind = 'unknown'
    issues: list[str] = []
    if not source_channel:
        issues.append('missing_source_channel')
    if source_kind == 'paid' and not tracking_token:
        issues.append('missing_tracking_token')
    if source_kind == 'paid' and not (click_id or session_id):
        issues.append('missing_click_or_session_linkage')
    refs = tuple(ref for ref in (source_channel, tracking_token, click_id, session_id) if ref)
    status = 'captured' if source_channel else 'missing'
    return SpendSourceFact(
        tenant_id=str(truth.get('tenant_id') or ''),
        business_id=str(truth.get('business_id') or ''),
        entity_id=str(truth.get('order_id') or ''),
        source_channel=source_channel,
        source_kind=source_kind,
        tracking_token=tracking_token,
        click_id=click_id,
        session_id=session_id,
        status=status,
        issues=tuple(issues),
        evidence_refs=refs,
        ready_for_export=bool(truth.get('reconciliation_consistent')) and bool(source_channel),
    )


def build_spend_source_manifest_from_client_outcome(*, truth_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    fact = build_spend_source_fact_from_client_outcome(truth_snapshot=truth_snapshot)
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
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    return {
        'algorithm': 'sha256',
        'hash': digest,
        'payload': payload,
        'verified': True,
        'domains_with_evidence': ('spend_source',) if fact.evidence_refs else tuple(),
        'evidence_ref_count': len(fact.evidence_refs),
    }



def build_spend_source_ingress_record_from_client_outcome(*, truth_snapshot: Mapping[str, Any]) -> SpendSourceIngressRecord:
    fact = build_spend_source_fact_from_client_outcome(truth_snapshot=truth_snapshot)
    blockers = list(fact.issues)
    stages: list[str] = []
    if fact.source_channel:
        stages.append('source_channel_bound')
    if fact.tracking_token:
        stages.append('tracking_token_bound')
    if fact.click_id or fact.session_id:
        stages.append('traffic_linkage_bound')
    if fact.status == 'captured' and not blockers:
        stages.append('spend_source_ingress_ready')
        status = 'ready'
    elif fact.status == 'captured':
        stages.append('spend_source_ingress_blocked')
        status = 'blocked'
    else:
        stages.append('spend_source_ingress_missing')
        status = 'missing'
    return SpendSourceIngressRecord(
        tenant_id=fact.tenant_id,
        business_id=fact.business_id,
        entity_id=fact.entity_id,
        source_channel=fact.source_channel,
        source_kind=fact.source_kind,
        tracking_token=fact.tracking_token,
        click_id=fact.click_id,
        session_id=fact.session_id,
        status=status,
        blockers=tuple(blockers),
        lifecycle_stages=tuple(stages),
        evidence_refs=fact.evidence_refs,
        ready_for_export=bool(fact.ready_for_export and status == 'ready'),
    )



def build_spend_ingress_envelope_from_client_outcome(*, truth_snapshot: Mapping[str, Any]) -> SpendIngressEnvelope:
    spend_fact = build_spend_fact_from_client_outcome(truth_snapshot=truth_snapshot)
    source_fact = build_spend_source_fact_from_client_outcome(truth_snapshot=truth_snapshot)
    blockers = list(spend_fact.issues) + list(source_fact.issues)
    stages: list[str] = []
    if spend_fact.amount_minor > 0:
        stages.append('spend_amount_bound')
    if source_fact.source_channel:
        stages.append('spend_source_channel_bound')
    if source_fact.tracking_token:
        stages.append('spend_tracking_bound')
    if source_fact.click_id or source_fact.session_id:
        stages.append('spend_traffic_linkage_bound')
    if spend_fact.amount_minor > 0 and source_fact.source_channel and not blockers:
        stages.append('spend_ingress_envelope_ready')
        status = 'ready'
    elif spend_fact.amount_minor > 0 or source_fact.source_channel:
        stages.append('spend_ingress_envelope_blocked')
        status = 'blocked'
    else:
        stages.append('spend_ingress_envelope_missing')
        status = 'missing'
    currency = 'USD'
    for candidate in (truth_snapshot.get('currency'), truth_snapshot.get('metadata', {}).get('currency') if isinstance(truth_snapshot.get('metadata'), Mapping) else None):
        c = str(candidate or '').strip()
        if c:
            currency = c.upper()
            break
    return SpendIngressEnvelope(
        tenant_id=spend_fact.tenant_id,
        business_id=spend_fact.business_id,
        entity_id=spend_fact.entity_id,
        amount_minor=spend_fact.amount_minor,
        currency=currency,
        source_channel=source_fact.source_channel,
        source_kind=source_fact.source_kind,
        tracking_token=source_fact.tracking_token,
        click_id=source_fact.click_id,
        session_id=source_fact.session_id,
        status=status,
        blockers=tuple(dict.fromkeys(str(item) for item in blockers if str(item).strip())),
        lifecycle_stages=tuple(dict.fromkeys(str(item) for item in stages if str(item).strip())),
        evidence_refs=tuple(dict.fromkeys((*spend_fact.evidence_refs, *source_fact.evidence_refs))),
        ready_for_export=bool(status == 'ready' and spend_fact.ready_for_export),
    )


def build_spend_ingress_manifest_from_client_outcome(*, truth_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    envelope = build_spend_ingress_envelope_from_client_outcome(truth_snapshot=truth_snapshot)
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
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    return {
        'algorithm': 'sha256',
        'hash': digest,
        'payload': payload,
        'verified': True,
        'domains_with_evidence': ('spend', 'spend_source') if envelope.evidence_refs else tuple(),
        'evidence_ref_count': len(envelope.evidence_refs),
    }



def build_spend_external_ingress_batch_from_client_outcome(*, truth_snapshot: Mapping[str, Any]) -> SpendExternalIngressBatch:
    envelope = build_spend_ingress_envelope_from_client_outcome(truth_snapshot=truth_snapshot)
    manifest = build_spend_ingress_manifest_from_client_outcome(truth_snapshot=truth_snapshot)
    blockers = list(envelope.blockers)
    stages = list(envelope.lifecycle_stages)
    batch_payload: dict[str, object] | None = None
    status = 'blocked'
    batch_id = f"spend-batch:{envelope.entity_id}" if str(envelope.entity_id).strip() else ''
    if envelope.status == 'ready' and envelope.amount_minor > 0:
        batch_payload = {
            'batch_id': batch_id,
            'amount_minor': envelope.amount_minor,
            'currency': envelope.currency,
            'source_channel': envelope.source_channel,
            'source_kind': envelope.source_kind,
            'manifest_hash': str(manifest.get('hash') or ''),
            'evidence_ref_count': len(tuple(envelope.evidence_refs or ())),
            'ingress_owner': 'spend.owner_path.external_ingress_projection',
        }
        stages.append('spend_external_ingress_batch_materialized')
        status = 'ready'
    else:
        blockers.append('spend_external_ingress_batch_not_ready')
        stages.append('spend_external_ingress_batch_blocked')
    return SpendExternalIngressBatch(
        tenant_id=envelope.tenant_id,
        business_id=envelope.business_id,
        entity_id=envelope.entity_id,
        batch_id=batch_id,
        amount_minor=envelope.amount_minor,
        currency=envelope.currency,
        source_channel=envelope.source_channel,
        source_kind=envelope.source_kind,
        status=status,
        blockers=tuple(dict.fromkeys(str(item) for item in blockers if str(item).strip())),
        lifecycle_stages=tuple(dict.fromkeys(str(item) for item in stages if str(item).strip())),
        evidence_refs=envelope.evidence_refs,
        ready_for_export=bool(envelope.ready_for_export and batch_payload is not None),
        batch_payload=batch_payload,
    )



def build_spend_external_ingress_runtime_request_from_client_outcome(*, truth_snapshot: Mapping[str, Any]) -> SpendExternalIngressRuntimeRequest:
    batch = build_spend_external_ingress_batch_from_client_outcome(truth_snapshot=truth_snapshot)
    manifest = build_spend_ingress_manifest_from_client_outcome(truth_snapshot=truth_snapshot)
    blockers = list(batch.blockers)
    stages = list(batch.lifecycle_stages)
    runtime_request: dict[str, object] | None = None
    status = 'blocked'
    if batch.batch_payload is not None and str((manifest.get('hash') or '')).strip():
        runtime_request = {
            'batch_id': batch.batch_id,
            'amount_minor': batch.amount_minor,
            'currency': batch.currency,
            'source_channel': batch.source_channel,
            'source_kind': batch.source_kind,
            'manifest_hash': str(manifest.get('hash') or ''),
            'transport_owner': 'runtime._internal.http_transport',
            'dispatch_owner': 'runtime._internal.effect_router',
            'idempotency_key': f"spend-runtime-request:{batch.entity_id}:{batch.batch_id}",
        }
        stages.append('spend_external_ingress_runtime_request_materialized')
        status = 'ready'
    else:
        blockers.append('spend_external_ingress_runtime_request_not_ready')
        stages.append('spend_external_ingress_runtime_request_blocked')
    return SpendExternalIngressRuntimeRequest(
        tenant_id=batch.tenant_id,
        business_id=batch.business_id,
        entity_id=batch.entity_id,
        batch_id=batch.batch_id,
        amount_minor=batch.amount_minor,
        currency=batch.currency,
        status=status,
        blockers=tuple(dict.fromkeys(str(item) for item in blockers if str(item).strip())),
        lifecycle_stages=tuple(dict.fromkeys(str(item) for item in stages if str(item).strip())),
        evidence_refs=batch.evidence_refs,
        ready_for_export=bool(batch.ready_for_export and runtime_request is not None),
        runtime_request=runtime_request,
    )
