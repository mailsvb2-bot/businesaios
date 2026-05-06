from execution.economic_audit_bundle import EconomicAuditBundleService
from execution.economic_multi_backend_reconciliation import EconomicMultiBackendReconciliationBuilder
from execution.economic_retention_policy import EconomicRetentionPolicy, apply_economic_retention_policy


def test_economic_retention_policy_prunes_bundle_segments() -> None:
    payload = {
        'feedback_rows': [{'event_id': f'e-{i}'} for i in range(5)],
        'roi_rows': [{'event_id': f'e-{i}'} for i in range(4)],
        'snapshot_rows': [{'snapshot_id': f's-{i}'} for i in range(3)],
        'trace_rows': [{'trace_id': f't-{i}'} for i in range(2)],
        'metrics_rows': [{'snapshot_id': f'm-{i}'} for i in range(6)],
        'audit_summary': {'ok': True},
        'metadata': {},
    }
    applied = apply_economic_retention_policy(
        payload=payload,
        retention_policy=EconomicRetentionPolicy(
            max_feedback_rows=2,
            max_roi_rows=2,
            max_snapshot_rows=1,
            max_trace_rows=1,
            max_metrics_rows=3,
        ),
    )
    assert len(applied.payload['feedback_rows']) == 2
    assert applied.payload['feedback_rows'][0]['event_id'] == 'e-3'
    assert applied.retention['segments']['metrics_rows']['dropped_count'] == 3


def test_economic_audit_bundle_builds_with_retention_manifest() -> None:
    service = EconomicAuditBundleService()
    bundle = service.build_bundle(
        bundle_id='bundle-1',
        feedback_rows=[{'event_id': f'e-{i}'} for i in range(4)],
        roi_rows=[{'event_id': f'e-{i}'} for i in range(4)],
        snapshot_rows=[{'snapshot_id': f's-{i}'} for i in range(2)],
        trace_rows=[{'trace_id': f't-{i}'} for i in range(2)],
        metrics_rows=[{'snapshot_id': f'm-{i}'} for i in range(4)],
        retention_policy={'max_feedback_rows': 2, 'max_roi_rows': 2, 'max_snapshot_rows': 1, 'max_trace_rows': 1, 'max_metrics_rows': 2},
    ).to_dict()
    assert len(bundle['payload']['feedback_rows']) == 2
    assert bundle['payload']['export_manifest']['retention']['segments']['feedback_rows']['retained_count'] == 2


def test_economic_multi_backend_reconciliation_detects_inconsistent_node() -> None:
    recon = EconomicMultiBackendReconciliationBuilder().build(
        feedback_rows=[{'event_id': 'evt-1'}],
        roi_rows=[{'event_id': 'evt-1'}],
        snapshot_rows=[{'snapshot_id': 'snap-1'}],
        trace_rows=[{'trace_id': 'trace-1'}],
        metrics_rows=[{'snapshot_id': 'evt-1'}],
        bundle_payloads=[{
            'payload': {
                'feedback_rows': [{'event_id': 'evt-1'}],
                'roi_rows': [{'event_id': 'evt-1'}],
                'snapshot_rows': [{'snapshot_id': 'snap-1'}],
                'trace_rows': [{'trace_id': 'trace-1'}],
                'metrics_rows': [{'snapshot_id': 'evt-1'}],
            }
        }],
        node_payloads=[
            {
                'node_id': 'node-a',
                'payload': {
                    'feedback_rows': [{'event_id': 'evt-1'}],
                    'roi_rows': [{'event_id': 'evt-1'}],
                    'snapshot_rows': [{'snapshot_id': 'snap-1'}],
                    'trace_rows': [{'trace_id': 'trace-1'}],
                    'metrics_rows': [{'snapshot_id': 'evt-1'}],
                },
            },
            {
                'node_id': 'node-b',
                'payload': {
                    'feedback_rows': [{'event_id': 'evt-2'}],
                    'roi_rows': [{'event_id': 'evt-1'}],
                    'snapshot_rows': [{'snapshot_id': 'snap-1'}],
                    'trace_rows': [{'trace_id': 'trace-1'}],
                    'metrics_rows': [{'snapshot_id': 'evt-1'}],
                },
            },
        ],
    ).to_dict()
    assert recon['consistent'] is False
    assert recon['node_count'] == 2
    assert recon['inconsistent_node_ids'] == ['node-b']


from execution.economic_export_manifest import manifest_payload_for_digest
from hashlib import sha256
import json


def test_economic_audit_bundle_recomputes_manifest_digest_after_retention_application() -> None:
    service = EconomicAuditBundleService()
    bundle = service.build_bundle(
        bundle_id='bundle-digest',
        feedback_rows=[{'event_id': 'e-1'}],
        roi_rows=[{'event_id': 'e-1'}],
        snapshot_rows=[{'snapshot_id': 's-1'}],
        trace_rows=[{'trace_id': 't-1'}],
        metrics_rows=[{'snapshot_id': 'm-1'}],
        retention_policy={'max_feedback_rows': 1, 'max_roi_rows': 1, 'max_snapshot_rows': 1, 'max_trace_rows': 1, 'max_metrics_rows': 1},
    ).to_dict()
    manifest = bundle['payload']['export_manifest']
    expected = sha256(json.dumps(manifest_payload_for_digest(manifest), ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    assert manifest['manifest_digest'] == expected
