from __future__ import annotations

from runtime.economic_core.attribution_bridge import (
    build_attribution_truth_fragment,
    build_attribution_truth_snapshot_from_client_outcome,
)


def test_attribution_truth_fragment_projects_provenance_without_creating_new_truth() -> None:
    snapshot = build_attribution_truth_snapshot_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-a',
            'business_id': 'biz-a',
            'order_id': 'order-a',
            'source_channel': 'ads',
            'reconciliation_consistent': True,
        },
        lifecycle={
            'lead': {'source_channel': 'ads', 'tracking_token': 'trk-a'},
            'stages': {
                'verified': {
                    'payload': {
                        'attributed': True,
                        'confidence': 0.92,
                        'proof_refs': ['crm:deal:a'],
                    },
                },
            },
        },
    )
    fragment = build_attribution_truth_fragment(attribution_snapshot=snapshot)
    assert fragment.domain == 'attribution'
    assert fragment.aggregation_mode == 'consistency_only'
    assert fragment.booked_amount_minor is None
    assert fragment.corrected_amount_minor is None
    assert 'source_channel_bound' in fragment.lifecycle_stages
    assert 'tracking_token_bound' in fragment.lifecycle_stages
    assert fragment.ready_for_export is True
