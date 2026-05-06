from __future__ import annotations

from runtime.economic_core.audit_provenance_bridge import build_audit_provenance_fragment, build_audit_provenance_snapshot
from economics.contracts import TruthFragment


def test_audit_provenance_fragment_projects_export_hash_and_evidence_without_new_truth() -> None:
    snapshot = build_audit_provenance_snapshot(
        truth_payload={'tenant_id': 'tenant-a', 'business_id': 'biz-a', 'order_id': 'order-a', 'value': 'x'},
        fragments=(
            TruthFragment(
                tenant_id='tenant-a',
                business_id='biz-a',
                domain='billing',
                entity_id='order-a',
                commercial_status='linked',
                lifecycle_stages=('invoice_linked',),
                booked_amount_minor=100,
                corrected_amount_minor=100,
                currency='USD',
                aggregation_mode='consistency_only',
                evidence_refs=('inv-1', 'provider:demo'),
                ready_for_export=True,
            ),
        ),
    )
    fragment = build_audit_provenance_fragment(audit_snapshot=snapshot)
    assert fragment.domain == 'audit_provenance'
    assert fragment.aggregation_mode == 'consistency_only'
    assert snapshot['verified'] is True
    assert snapshot['evidence_ref_count'] == 2
    assert 'billing' in snapshot['domains_with_evidence']
    assert fragment.ready_for_export is True
