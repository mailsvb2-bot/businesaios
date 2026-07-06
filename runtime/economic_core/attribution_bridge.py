from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from economics.contracts import TruthFragment

CANON_RUNTIME_ECONOMIC_CORE_ATTRIBUTION_BRIDGE = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def build_attribution_truth_snapshot_from_client_outcome(*, truth_snapshot: Mapping[str, Any], lifecycle: object | None) -> dict[str, Any]:
    """Read-only attribution/provenance projection for Economic OS.

    This bridge must not make a new attribution decision. It only projects the
    already-produced client-outcome/lifecycle truth into a canonical fragment.
    """
    truth = dict(truth_snapshot)
    lifecycle_payload = _safe_dict(lifecycle)
    stages = _safe_dict(lifecycle_payload.get('stages'))
    verified_stage = _safe_dict(stages.get('verified'))
    verified_payload = _safe_dict(verified_stage.get('payload'))
    lead_payload = _safe_dict(lifecycle_payload.get('lead'))
    captured_stage = _safe_dict(stages.get('lead_captured'))
    captured_payload = _safe_dict(captured_stage.get('payload'))
    source_channel = str(truth.get('source_channel') or captured_payload.get('source_channel') or lead_payload.get('source_channel') or '').strip()
    tracking_token = str(truth.get('tracking_token') or captured_payload.get('tracking_token') or lead_payload.get('tracking_token') or '').strip()
    proof_refs = tuple(str(item).strip() for item in tuple(verified_payload.get('proof_refs') or ()) if str(item).strip())
    attributed = bool(verified_payload.get('attributed'))
    confidence_raw = verified_payload.get('confidence')
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0
    status = 'attributed' if attributed and source_channel else ('pending' if source_channel else 'unknown')
    issues: list[str] = []
    if attributed and not source_channel:
        issues.append('attributed_without_source_channel')
    if not tracking_token:
        issues.append('missing_tracking_token')
    return {
        'tenant_id': str(truth.get('tenant_id') or ''),
        'business_id': str(truth.get('business_id') or ''),
        'entity_id': str(truth.get('order_id') or ''),
        'attribution_status': status,
        'source_channel': source_channel,
        'tracking_token_present': bool(tracking_token),
        'proof_refs': proof_refs,
        'proof_ref_count': len(proof_refs),
        'attributed': attributed,
        'confidence': confidence,
        'ready_for_export': bool(truth.get('reconciliation_consistent')) and attributed,
        'issues': tuple(issues),
    }


def build_attribution_truth_fragment(*, attribution_snapshot: Mapping[str, Any]) -> TruthFragment:
    snapshot = dict(attribution_snapshot)
    source_channel = str(snapshot.get('source_channel') or '').strip()
    evidence_refs = tuple(
        item
        for item in ((source_channel,) + tuple(str(ref) for ref in tuple(snapshot.get('proof_refs') or ())))
        if item
    )
    lifecycle_stages: tuple[str, ...] = tuple()
    if source_channel:
        lifecycle_stages += ('source_channel_bound',)
    if bool(snapshot.get('tracking_token_present')):
        lifecycle_stages += ('tracking_token_bound',)
    if int(snapshot.get('proof_ref_count') or 0) > 0:
        lifecycle_stages += ('proof_refs_observed',)
    return TruthFragment(
        tenant_id=str(snapshot.get('tenant_id') or ''),
        business_id=str(snapshot.get('business_id') or ''),
        domain='attribution',
        entity_id=str(snapshot.get('entity_id') or ''),
        commercial_status=str(snapshot.get('attribution_status') or 'unknown'),
        lifecycle_stages=lifecycle_stages,
        booked_amount_minor=None,
        corrected_amount_minor=None,
        currency=None,
        aggregation_mode='consistency_only',
        issues=tuple(str(item) for item in tuple(snapshot.get('issues') or ())),
        evidence_refs=evidence_refs,
        ready_for_export=bool(snapshot.get('ready_for_export')),
    )
