from datetime import UTC, datetime, timedelta

from execution.economic_audit_bundle import EconomicAuditBundleService
from execution.economic_multi_backend_reconciliation import EconomicMultiBackendReconciliationBuilder
from execution.economic_retention_policy import EconomicRetentionPolicy, apply_economic_retention_policy


def test_economic_retention_policy_prunes_by_age_and_count() -> None:
    now = datetime.now(UTC)
    payload = {
        'feedback_rows': [
            {'event_id': 'old-1', 'created_at': (now - timedelta(days=50)).isoformat()},
            {'event_id': 'mid-1', 'created_at': (now - timedelta(days=10)).isoformat()},
            {'event_id': 'new-1', 'created_at': now.isoformat()},
        ],
        'roi_rows': [
            {'event_id': 'roi-old', 'created_at': (now - timedelta(days=50)).isoformat()},
            {'event_id': 'roi-new', 'created_at': now.isoformat()},
        ],
        'snapshot_rows': [],
        'trace_rows': [],
        'metrics_rows': [],
        'audit_summary': {'ok': True},
        'metadata': {},
    }
    applied = apply_economic_retention_policy(
        payload=payload,
        retention_policy=EconomicRetentionPolicy(max_feedback_rows=1, max_roi_rows=5, max_age_days=30),
        reference_time=now,
    )
    assert [row['event_id'] for row in applied.payload['feedback_rows']] == ['new-1']
    assert [row['event_id'] for row in applied.payload['roi_rows']] == ['roi-new']
    assert applied.retention['segments']['feedback_rows']['age_dropped_count'] == 1


def test_economic_bundle_manifest_carries_manifest_digest_and_retention() -> None:
    service = EconomicAuditBundleService()
    bundle = service.build_bundle(
        bundle_id='bundle-1',
        feedback_rows=[{'event_id': 'e-1', 'created_at': datetime.now(UTC).isoformat()}],
        roi_rows=[],
        snapshot_rows=[],
        trace_rows=[],
        metrics_rows=[],
        retention_policy={'max_feedback_rows': 5, 'max_age_days': 30},
    ).to_dict()
    manifest = bundle['payload']['export_manifest']
    assert manifest['retention']['segments']['feedback_rows']['retained_count'] == 1


def test_economic_multi_backend_reconciliation_reports_quorum() -> None:
    recon = EconomicMultiBackendReconciliationBuilder().build(
        feedback_rows=[{'event_id': 'evt-1'}],
        roi_rows=[{'event_id': 'evt-1'}],
        snapshot_rows=[{'snapshot_id': 'snap-1'}],
        trace_rows=[{'trace_id': 'trace-1'}],
        metrics_rows=[{'snapshot_id': 'metric-1'}],
        bundle_payloads=[{'payload': {'feedback_rows': [{'event_id': 'evt-1'}], 'roi_rows': [{'event_id': 'evt-1'}], 'snapshot_rows': [{'snapshot_id': 'snap-1'}], 'trace_rows': [{'trace_id': 'trace-1'}], 'metrics_rows': [{'snapshot_id': 'metric-1'}]}}],
        node_payloads=[
            {'node_id': 'node-a', 'payload': {'feedback_rows': [{'event_id': 'evt-1'}], 'roi_rows': [{'event_id': 'evt-1'}], 'snapshot_rows': [{'snapshot_id': 'snap-1'}], 'trace_rows': [{'trace_id': 'trace-1'}], 'metrics_rows': [{'snapshot_id': 'metric-1'}]}},
            {'node_id': 'node-b', 'payload': {'feedback_rows': [{'event_id': 'evt-1'}], 'roi_rows': [{'event_id': 'evt-1'}], 'snapshot_rows': [{'snapshot_id': 'snap-1'}], 'trace_rows': [{'trace_id': 'trace-1'}], 'metrics_rows': [{'snapshot_id': 'metric-1'}]}},
            {'node_id': 'node-c', 'payload': {'feedback_rows': [{'event_id': 'evt-9'}], 'roi_rows': [{'event_id': 'evt-1'}], 'snapshot_rows': [{'snapshot_id': 'snap-1'}], 'trace_rows': [{'trace_id': 'trace-1'}], 'metrics_rows': [{'snapshot_id': 'metric-1'}]}},
        ],
        quorum_size=2,
    ).to_dict()
    assert recon['quorum_achieved'] is True
    assert recon['segment_quorum']['feedback']['support_count'] == 2
    assert recon['inconsistent_node_ids'] == ['node-c']
