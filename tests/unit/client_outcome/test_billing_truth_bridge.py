from __future__ import annotations

from runtime.economic_core.billing_bridge import (
    build_billing_truth_fragment,
    build_billing_truth_snapshot_from_client_outcome,
)


def test_billing_truth_bridge_projects_refund_materialization_from_client_outcome_truth() -> None:
    truth = {
        'tenant_id': 'tenant-1',
        'business_id': 'biz-1',
        'order_id': 'order-1',
        'commercial_status': 'reversed',
        'reconciliation_consistent': True,
        'corrected_revenue': {'billed_revenue': 0.0, 'currency': 'USD'},
        'issues': (),
    }
    corrected = {
        'refund_request': {
            'invoice_id': 'inv-1',
            'provider_name': 'demo',
            'amount_minor': 2500,
            'currency': 'USD',
        },
        'corrected_revenue': {'billed_revenue': 0.0, 'currency': 'USD'},
        'reversal': {'amount': 25.0, 'currency': 'USD'},
    }
    snapshot = build_billing_truth_snapshot_from_client_outcome(truth_snapshot=truth, corrected_economics=corrected)
    fragment = build_billing_truth_fragment(billing_snapshot=snapshot)

    assert snapshot['billing_status'] == 'refunded'
    assert snapshot['refund_total_minor'] == 2500
    assert fragment.domain == 'billing'
    assert fragment.lifecycle_stages[-1] == 'refund_materialized'
    assert fragment.aggregation_mode == 'consistency_only'
    assert fragment.evidence_refs == ('inv-1', 'demo')
