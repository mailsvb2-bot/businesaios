from execution.economic_schema_validation import EconomicSchemaValidator
from execution.economic_segment_validation import EconomicSegmentValidator
from execution.economic_semantic_validation import EconomicSemanticValidator
from execution.economic_split_brain_guard import EconomicSplitBrainGuard
from execution.economic_anchor_preservation import EconomicAnchorPreservationChecker


def test_schema_validator_rejects_legacy_bundle() -> None:
    verdict = EconomicSchemaValidator().validate(payload={'export_manifest': {'bundle_schema_version': '1'}})
    assert verdict.compatible is False


def test_segment_validator_detects_incomplete_payload() -> None:
    verdict = EconomicSegmentValidator().validate(payload={'feedback_rows': []})
    assert verdict.complete is False


def test_semantic_validator_detects_disconnected_roi() -> None:
    verdict = EconomicSemanticValidator().validate(
        payload={
            'feedback_rows': [{'event_id': 'f1'}],
            'roi_rows': [{'event_id': 'r1'}],
            'trace_rows': [{'trace_id': 't1'}],
            'snapshot_rows': [{'snapshot_id': 's1'}],
            'metrics_rows': [{'snapshot_id': 'm1'}],
            'export_manifest': {'scope': {'tenant_id': 't1'}},
        }
    )
    assert verdict.valid is False


def test_split_brain_guard_marks_stale_nodes() -> None:
    verdict = EconomicSplitBrainGuard().build(
        node_views=[
            {'node_id': 'a', 'leader_epoch': 1, 'fencing_token': '1', 'active': True, 'store_digest': 'x'},
            {'node_id': 'b', 'leader_epoch': 2, 'fencing_token': '2', 'active': True, 'store_digest': 'y'},
        ]
    )
    assert verdict.split_brain_detected is True
    assert verdict.authoritative_node_id == 'b'


def test_anchor_preservation_detects_missing_anchor() -> None:
    verdict = EconomicAnchorPreservationChecker().validate(
        payload={'feedback_rows': [{'event_id': 'e1'}]},
        required_anchor_ids=('e1', 'e2'),
    )
    assert verdict.preserved is False
    assert 'e2' in verdict.missing_anchor_ids
