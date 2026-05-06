from __future__ import annotations

import json
from pathlib import Path

import pytest

from execution.economic_audit_bundle import EconomicAuditBundleService
from execution.economic_export_manifest import validate_economic_export_manifest
from execution.economic_multi_backend_reconciliation import EconomicMultiBackendReconciliationBuilder


def test_export_manifest_validation_detects_digest_and_profile_drift() -> None:
    service = EconomicAuditBundleService()
    manifest = service.build_export_manifest(
        stores={},
        node_id='node-a',
        scope={
            'tenant_id': 'tenant-a',
            'business_id': 'biz-a',
            'tenant_tier': 'standard',
            'business_tier': 'standard',
            'profile_name': 'standard',
        },
    )
    manifest['scope']['profile_name'] = 'regulated'
    validation = validate_economic_export_manifest(
        manifest=manifest,
        expected_scope={'tenant_id': 'tenant-a', 'business_id': 'biz-a', 'profile_name': 'standard'},
        expected_profile_name='standard',
    )
    assert validation['valid'] is False
    assert 'manifest_digest_mismatch' in validation['issues']
    assert 'scope_profile_name_mismatch' in validation['issues'] or 'profile_name_mismatch' in validation['issues']


def test_restore_bundle_fails_closed_on_scope_profile_drift(tmp_path: Path) -> None:
    service = EconomicAuditBundleService()
    scope = {
        'tenant_id': 'tenant-a',
        'business_id': 'biz-a',
        'tenant_tier': 'standard',
        'business_tier': 'standard',
        'profile_name': 'standard',
    }
    manifest = service.build_export_manifest(stores={}, node_id='node-a', scope=scope)
    bundle = service.build_bundle(
        bundle_id='evt-1',
        feedback_rows=[{'event_id': 'evt-1'}],
        roi_rows=[],
        snapshot_rows=[],
        trace_rows=[],
        metrics_rows=[],
        export_manifest=manifest,
        scope_profile=scope,
    )
    path = tmp_path / 'bundle.json'
    service.export_json(bundle=bundle, path=path)
    raw = json.loads(path.read_text(encoding='utf-8'))
    raw['payload']['export_manifest']['scope']['tenant_id'] = 'tenant-z'
    path.write_text(json.dumps(raw), encoding='utf-8')
    with pytest.raises(ValueError, match='economic bundle validation failed'):
        service.restore_bundle(
            bundle_path=path,
            strict_validation=True,
            expected_scope=scope,
            expected_profile_name='standard',
        )


def test_reconciliation_detects_profile_mismatch_nodes() -> None:
    recon = EconomicMultiBackendReconciliationBuilder().build(
        feedback_rows=[{'event_id': 'evt-1'}],
        roi_rows=[],
        snapshot_rows=[],
        trace_rows=[],
        metrics_rows=[],
        bundle_payloads=[{'payload': {'feedback_rows': [{'event_id': 'evt-1'}], 'export_manifest': {'scope': {'tenant_id': 'tenant-a', 'business_id': 'biz-a', 'profile_name': 'standard'}}}}],
        node_payloads=[
            {'node_id': 'node-a', 'payload': {'feedback_rows': [{'event_id': 'evt-1'}], 'export_manifest': {'scope': {'tenant_id': 'tenant-a', 'business_id': 'biz-a', 'profile_name': 'standard'}}}},
            {'node_id': 'node-b', 'payload': {'feedback_rows': [{'event_id': 'evt-1'}], 'export_manifest': {'scope': {'tenant_id': 'tenant-a', 'business_id': 'biz-a', 'profile_name': 'regulated'}}}},
        ],
        quorum_size=1,
    ).to_dict()
    assert recon['profile_mismatch_node_ids'] == ['node-b']
    assert recon['consistent'] is False
