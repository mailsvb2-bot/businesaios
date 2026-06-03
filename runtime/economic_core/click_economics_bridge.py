from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from click_economics.public_api import (
    build_click_billable_fact_contract_from_client_outcome,
    build_click_billable_fact_from_client_outcome,
    build_click_commercial_fact_from_client_outcome,
)
from economics.contracts import TruthFragment

CANON_RUNTIME_ECONOMIC_CORE_CLICK_ECONOMICS_BRIDGE = True


def build_click_economics_truth_snapshot_from_client_outcome(*, truth_snapshot: Mapping[str, Any], lifecycle: object | None) -> dict[str, Any]:
    """Canonical click-economics projection.

    Uses the dedicated click_economics public API to normalize already-owned
    click/session/tracking facts from the client-outcome contour. It does not
    create a new revenue owner or duplicate billing logic.
    """
    fact = build_click_commercial_fact_from_client_outcome(truth_snapshot=truth_snapshot, lifecycle=lifecycle)
    billable_fact = build_click_billable_fact_from_client_outcome(truth_snapshot=truth_snapshot, lifecycle=lifecycle)
    billable_contract = build_click_billable_fact_contract_from_client_outcome(truth_snapshot=truth_snapshot, lifecycle=lifecycle)
    return {
        'tenant_id': fact.tenant_id,
        'business_id': fact.business_id,
        'entity_id': fact.entity_id,
        'click_status': fact.status,
        'click_id_present': bool(fact.click_id),
        'session_id_present': bool(fact.session_id),
        'source_channel': fact.source_channel,
        'tracking_token_present': bool(fact.tracking_token),
        'billable_candidate': fact.billable_candidate,
        'click_billable_fact_ready': billable_contract is not None,
        'click_billable_fact': None if billable_contract is None else {
            'domain': billable_contract.domain,
            'entity_id': billable_contract.entity_id,
            'amount_minor': billable_contract.amount_minor,
            'currency': billable_contract.currency,
            'reason_code': billable_contract.reason_code,
            'idempotency_key': billable_contract.idempotency_key,
        },
        'click_price_minor': None if billable_fact is None else billable_fact.amount_minor,
        'click_currency': '' if billable_fact is None else billable_fact.currency,
        'proof_refs': fact.evidence_refs if billable_fact is None else billable_fact.evidence_refs,
        'issues': fact.issues if billable_fact is None else billable_fact.issues,
        'ready_for_export': fact.ready_for_export if billable_fact is None else billable_fact.ready_for_export,
    }


def build_click_economics_truth_fragment(*, click_snapshot: Mapping[str, Any]) -> TruthFragment:
    snapshot = dict(click_snapshot)
    lifecycle_stages: tuple[str, ...] = tuple()
    if bool(snapshot.get('click_id_present')):
        lifecycle_stages += ('click_id_bound',)
    if bool(snapshot.get('session_id_present')):
        lifecycle_stages += ('session_id_bound',)
    if str(snapshot.get('source_channel') or '').strip():
        lifecycle_stages += ('traffic_channel_observed',)
    if bool(snapshot.get('billable_candidate')):
        lifecycle_stages += ('click_candidate_identified',)
    if bool(snapshot.get('click_billable_fact_ready')):
        lifecycle_stages += ('click_billable_fact_ready',)
    return TruthFragment(
        tenant_id=str(snapshot.get('tenant_id') or ''),
        business_id=str(snapshot.get('business_id') or ''),
        domain='click_economics',
        entity_id=str(snapshot.get('entity_id') or ''),
        commercial_status=str(snapshot.get('click_status') or 'unknown'),
        lifecycle_stages=lifecycle_stages,
        booked_amount_minor=None,
        corrected_amount_minor=None,
        currency=None,
        aggregation_mode='consistency_only',
        issues=tuple(str(item) for item in tuple(snapshot.get('issues') or ())),
        evidence_refs=tuple(str(item) for item in tuple(snapshot.get('proof_refs') or ()) if str(item).strip()),
        ready_for_export=bool(snapshot.get('ready_for_export')),
    )
