from __future__ import annotations

from typing import Any, Iterable, Mapping

from economics.contracts import TruthFragment
from runtime.export.client_outcome_export import (
    export_client_outcome_truth_snapshot,
    verify_client_outcome_truth_export,
)

CANON_RUNTIME_ECONOMIC_CORE_AUDIT_PROVENANCE_BRIDGE = True


def build_audit_provenance_snapshot(*, truth_payload: Mapping[str, Any], fragments: Iterable[TruthFragment | None]) -> dict[str, Any]:
    fragment_list = tuple(fragment for fragment in fragments if hasattr(fragment, 'domain'))
    exported = export_client_outcome_truth_snapshot(truth_payload)
    evidence_refs: list[str] = []
    domains_with_evidence: list[str] = []
    for fragment in fragment_list:
        refs = tuple(str(item) for item in tuple(getattr(fragment, 'evidence_refs', ()) or ()) if str(item).strip())
        if refs:
            domains_with_evidence.append(str(getattr(fragment, 'domain', '')))
            evidence_refs.extend(refs)
    issues: list[str] = []
    if not verify_client_outcome_truth_export(exported):
        issues.append('export_hash_verification_failed')
    if not evidence_refs:
        issues.append('missing_evidence_refs')
    deduped_refs = tuple(dict.fromkeys(evidence_refs))
    deduped_domains = tuple(dict.fromkeys(item for item in domains_with_evidence if item))
    return {
        'tenant_id': str(truth_payload.get('tenant_id') or ''),
        'business_id': str(truth_payload.get('business_id') or ''),
        'entity_id': str(truth_payload.get('order_id') or truth_payload.get('scope_order_id') or ''),
        'audit_status': 'verifiable' if not issues else 'attention_required',
        'algorithm': str(exported.get('algorithm') or 'sha256'),
        'hash': str(exported.get('hash') or ''),
        'verified': verify_client_outcome_truth_export(exported),
        'evidence_refs': deduped_refs,
        'evidence_ref_count': len(deduped_refs),
        'domains_with_evidence': deduped_domains,
        'issues': tuple(issues),
        'ready_for_export': not bool(issues),
    }


def build_audit_provenance_fragment(*, audit_snapshot: Mapping[str, Any]) -> TruthFragment:
    snapshot = dict(audit_snapshot)
    issues = tuple(str(item) for item in tuple(snapshot.get('issues') or ()))
    return TruthFragment(
        tenant_id=str(snapshot.get('tenant_id') or ''),
        business_id=str(snapshot.get('business_id') or ''),
        domain='audit_provenance',
        entity_id=str(snapshot.get('entity_id') or ''),
        commercial_status=str(snapshot.get('audit_status') or 'attention_required'),
        lifecycle_stages=('evidence_attached',) if int(snapshot.get('evidence_ref_count') or 0) > 0 else ('evidence_missing',),
        booked_amount_minor=None,
        corrected_amount_minor=None,
        currency=None,
        aggregation_mode='consistency_only',
        issues=issues,
        evidence_refs=tuple(str(item) for item in tuple(snapshot.get('evidence_refs') or ())),
        ready_for_export=bool(snapshot.get('ready_for_export')),
    )
