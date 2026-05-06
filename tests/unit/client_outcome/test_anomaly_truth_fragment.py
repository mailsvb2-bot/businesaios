from __future__ import annotations

from runtime.economic_core.anomaly_bridge import build_anomaly_truth_fragment, build_anomaly_truth_snapshot
from runtime.economic_core.export_readiness_bridge import build_export_readiness_snapshot


def test_anomaly_truth_fragment_projects_existing_inconsistencies_without_creating_new_truth() -> None:
    anomaly = build_anomaly_truth_snapshot(
        reconciliation={
            'tenant_id': 'tenant-a',
            'business_id': 'biz-a',
            'order_id': 'order-a',
            'consistent': False,
            'issues': ('missing_refund_request',),
            'reversal_amount': None,
        },
        billing_snapshot={'refund_total_minor': 2500},
        attribution_snapshot={'attributed': True, 'source_channel': '', 'tracking_token_present': False},
    )
    fragment = build_anomaly_truth_fragment(anomaly_snapshot=anomaly)
    assert fragment.domain == 'anomaly'
    assert fragment.aggregation_mode == 'consistency_only'
    assert 'reconciliation_mismatch' in fragment.issues
    assert 'refund_without_reversal' in fragment.issues
    assert 'missing_attribution_source' in fragment.issues
    assert fragment.ready_for_export is False


def test_export_readiness_blocks_when_anomalies_are_present() -> None:
    readiness = build_export_readiness_snapshot(
        reconciliation={'tenant_id': 'tenant-a', 'business_id': 'biz-a', 'order_id': 'order-a', 'consistent': True},
        anomaly_snapshot={'has_issues': True},
    )
    assert readiness['ready'] is False
    assert 'anomalies_present' in readiness['blockers']
