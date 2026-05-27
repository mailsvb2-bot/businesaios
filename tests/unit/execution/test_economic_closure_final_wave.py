from __future__ import annotations

import json
from pathlib import Path

import pytest

from execution.economic_audit_bundle import EconomicAuditBundleService
from execution.economic_bundle_quarantine_store import InMemoryEconomicBundleQuarantineStore
from execution.economic_lineage_lock import EconomicLineageLockBuilder
from execution.economic_multi_backend_reconciliation import EconomicMultiBackendReconciliationBuilder
from execution.economic_state_monotonicity import EconomicStateMonotonicityGuard


def _scope(profile_name: str = 'standard') -> dict[str, str]:
    return {
        'tenant_id': 'tenant-a',
        'business_id': 'biz-a',
        'tenant_tier': 'standard',
        'business_tier': 'standard',
        'profile_name': profile_name,
    }


def test_lineage_lock_rejects_forked_parents() -> None:
    manifest = {
        'scope': _scope(),
        'scope_lineage': {'parents': [{'scope': {'tenant_id': 'tenant-a'}}, {'scope': {'tenant_id': 'tenant-b'}}]},
        'lineage_lock': {'lineage_hash': EconomicLineageLockBuilder().build_hash(scope=_scope(), scope_lineage={'parents': []}), 'parents': [{'a': 1}, {'b': 2}]},
    }
    verdict = EconomicLineageLockBuilder().validate(manifest=manifest, expected_scope=_scope())
    assert verdict.valid is False
    assert verdict.reason == 'economic_lineage_fork_detected'


def test_state_monotonicity_rejects_verified_revenue_rollback() -> None:
    verdict = EconomicStateMonotonicityGuard().validate(
        current_state={'meta': {'economic_feedback_history': [{'verified': True, 'realized_revenue': 100.0}] }},
        incoming_payload={'feedback_rows': [{'verified': True, 'realized_revenue': 50.0}]},
    )
    assert verdict.valid is False
    assert verdict.reason == 'economic_verified_revenue_rollback'


def test_restore_bundle_rejects_immutable_digest_mismatch(tmp_path: Path) -> None:
    quarantine = InMemoryEconomicBundleQuarantineStore()
    service = EconomicAuditBundleService(quarantine_sink=quarantine)
    scope = _scope()
    manifest = service.build_export_manifest(stores={}, node_id='node-a', scope=scope, scope_lineage={'old_scope': scope, 'new_scope': scope})
    bundle = service.build_bundle(
        bundle_id='evt-1',
        feedback_rows=[{'event_id': 'evt-1', 'verified': True, 'realized_revenue': 100.0}],
        roi_rows=[],
        snapshot_rows=[{'snapshot_id': 'snap-1'}],
        trace_rows=[{'trace_id': 'trace-1', 'event_id': 'evt-1'}],
        metrics_rows=[{'snapshot_id': 'snap-1'}],
        export_manifest=manifest,
        scope_profile=scope,
    )
    path = tmp_path / 'bundle.json'
    service.export_json(bundle=bundle, path=path)
    raw = json.loads(path.read_text(encoding='utf-8'))
    raw['payload']['feedback_rows'][0]['realized_revenue'] = 99.0
    path.write_text(json.dumps(raw), encoding='utf-8')

    with pytest.raises(ValueError, match='economic bundle validation failed'):
        service.restore_bundle(
            bundle_path=path,
            strict_validation=True,
            expected_scope=scope,
            expected_profile_name='standard',
        )


def test_reconciliation_emits_deterministic_merge_order_and_lineage_invalid_node() -> None:
    builder = EconomicMultiBackendReconciliationBuilder()
    result = builder.build(
        feedback_rows=[],
        roi_rows=[],
        snapshot_rows=[],
        trace_rows=[],
        metrics_rows=[],
        bundle_payloads=[],
        node_payloads=[
            {'node_id': 'node-b', 'leader_epoch': 1, 'payload': {'export_manifest': {'scope': _scope(), 'lineage_lock': {'lineage_hash': 'bad', 'parents': []}, 'generated_at': '2026-01-01T00:00:00+00:00', 'manifest_digest': 'bbb'}, 'metadata': {}}},
            {'node_id': 'node-a', 'leader_epoch': 2, 'payload': {'export_manifest': {'scope': _scope(), 'lineage_lock': {'lineage_hash': EconomicLineageLockBuilder().build_hash(scope=_scope(), scope_lineage={}), 'parents': []}, 'generated_at': '2026-01-01T00:00:00+00:00', 'manifest_digest': 'aaa'}, 'metadata': {}}},
        ],
        quorum_size=2,
    )
    meta = result.metadata
    assert meta['deterministic_merge_order'][0] == 'node-a'
    assert 'node-b' in meta['lineage_invalid_node_ids']
