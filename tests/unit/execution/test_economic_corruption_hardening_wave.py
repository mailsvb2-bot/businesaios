from __future__ import annotations

import json
from pathlib import Path

import pytest

from execution.economic_audit_bundle import EconomicAuditBundleService, validate_economic_bundle_payload
from execution.economic_bundle_quarantine import InMemoryEconomicBundleQuarantine
from execution.economic_multi_backend_reconciliation import EconomicMultiBackendReconciliationBuilder


def test_bundle_validation_detects_payload_digest_mismatch() -> None:
    service = EconomicAuditBundleService()
    bundle = service.build_bundle(
        bundle_id='evt-1',
        feedback_rows=[{'event_id': 'evt-1'}],
        roi_rows=[],
        snapshot_rows=[],
        trace_rows=[],
        metrics_rows=[],
    ).to_dict()
    bundle['digest'] = 'broken-digest'
    validation = validate_economic_bundle_payload(bundle=bundle)
    assert validation['valid'] is False
    assert 'bundle_digest_mismatch' in validation['issues']


def test_import_json_quarantines_invalid_bundle(tmp_path: Path) -> None:
    quarantine = InMemoryEconomicBundleQuarantine()
    service = EconomicAuditBundleService(quarantine_sink=quarantine)
    bundle = service.build_bundle(
        bundle_id='evt-1',
        feedback_rows=[{'event_id': 'evt-1'}],
        roi_rows=[],
        snapshot_rows=[],
        trace_rows=[],
        metrics_rows=[],
        scope_profile={'tenant_id': 'tenant-a', 'business_id': 'biz-a', 'profile_name': 'standard'},
        export_manifest=service.build_export_manifest(stores={}, scope={'tenant_id': 'tenant-a', 'business_id': 'biz-a', 'profile_name': 'standard'}),
    )
    path = tmp_path / 'bundle.json'
    service.export_json(bundle=bundle, path=path)
    raw = json.loads(path.read_text(encoding='utf-8'))
    raw['digest'] = 'broken-digest'
    path.write_text(json.dumps(raw), encoding='utf-8')
    with pytest.raises(ValueError, match='economic bundle validation failed'):
        service.import_json(path=path, strict_validation=True)
    rows = quarantine.list_rows()
    assert len(rows) == 1
    assert rows[0].reason == 'economic_bundle_validation_failed'
    assert 'bundle_digest_mismatch' in rows[0].issues


def test_reconciliation_reports_corrupted_nodes_and_quorum_failure() -> None:
    recon = EconomicMultiBackendReconciliationBuilder().build(
        feedback_rows=[{'event_id': 'evt-1'}],
        roi_rows=[],
        snapshot_rows=[],
        trace_rows=[],
        metrics_rows=[],
        bundle_payloads=[{'payload': {'feedback_rows': [{'event_id': 'evt-1'}]}}],
        node_payloads=[
            {'node_id': 'node-a', 'payload': {'feedback_rows': [{'event_id': 'evt-1'}], 'metadata': {'import_validation_status': 'valid'}}},
            {'node_id': 'node-b', 'payload': {'feedback_rows': [{'event_id': 'evt-2'}], 'metadata': {'import_validation_status': 'invalid'}, 'export_manifest': {'manifest_digest': 'corrupt'}}},
        ],
        quorum_size=2,
    ).to_dict()
    assert recon['corrupted_node_ids'] == ['node-b']
    assert 'feedback' in recon['quorum_failure_segments']
    assert recon['consistent'] is False
