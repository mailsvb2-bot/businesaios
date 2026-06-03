from __future__ import annotations

from collections.abc import Mapping

from economics.contracts import TruthFragment
from spend.public_api import build_spend_fact_from_client_outcome

CANON_RUNTIME_ECONOMIC_CORE_SPEND_BRIDGE = True


def build_spend_truth_snapshot_from_client_outcome(*, truth_snapshot: Mapping[str, object]) -> dict[str, object]:
    """Canonical spend projection.

    The spend owner-surface now comes from the dedicated spend public API, fed
    by already-persisted client-outcome truth. No new spend truth is invented in
    Economic OS.
    """
    fact = build_spend_fact_from_client_outcome(truth_snapshot=truth_snapshot)
    return {
        'tenant_id': fact.tenant_id,
        'business_id': fact.business_id,
        'entity_id': fact.entity_id,
        'spend_status': fact.status,
        'spend_total_minor': fact.amount_minor,
        'unit_cost_minor': fact.unit_cost_minor,
        'source_channel': fact.source_channel,
        'issues': fact.issues,
        'evidence_refs': fact.evidence_refs,
        'ready_for_export': fact.ready_for_export,
    }


def build_spend_truth_fragment(*, spend_snapshot: Mapping[str, object]) -> TruthFragment:
    snapshot = dict(spend_snapshot)
    lifecycle_stages = ('spend_fact_attached',) if int(snapshot.get('spend_total_minor') or 0) > 0 else ('spend_fact_missing',)
    return TruthFragment(
        tenant_id=str(snapshot.get('tenant_id') or ''),
        business_id=str(snapshot.get('business_id') or ''),
        domain='spend',
        entity_id=str(snapshot.get('entity_id') or ''),
        commercial_status=str(snapshot.get('spend_status') or 'missing'),
        lifecycle_stages=lifecycle_stages,
        booked_amount_minor=None,
        corrected_amount_minor=None,
        currency=None,
        cost_total_minor=int(snapshot.get('spend_total_minor') or 0),
        unit_cost_minor=None if snapshot.get('unit_cost_minor') is None else int(snapshot.get('unit_cost_minor')),
        aggregation_mode='cost_primary',
        issues=tuple(str(item) for item in tuple(snapshot.get('issues') or ())),
        evidence_refs=tuple(str(item) for item in tuple(snapshot.get('evidence_refs') or ()) if str(item).strip()),
        ready_for_export=bool(snapshot.get('ready_for_export')),
    )
