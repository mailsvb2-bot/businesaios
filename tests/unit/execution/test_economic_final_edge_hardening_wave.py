from __future__ import annotations

import json
from pathlib import Path

import pytest

from execution.economic_audit_bundle import EconomicAuditBundleService
from execution.economic_backend_authority import EconomicBackendAuthorityResolver
from execution.economic_bundle_quarantine_store import InMemoryEconomicBundleQuarantineStore
from execution.economic_scope_lineage import EconomicScopeLineageGuard
from execution.economic_semantic_validation import EconomicSemanticValidator
from execution.economic_split_brain_guard import EconomicSplitBrainGuard


def test_semantic_validator_detects_budget_guard_bypass_and_memory_without_anchor() -> None:
    verdict = EconomicSemanticValidator().validate(
        payload={
            'feedback_rows': [{'event_id': 'evt-1'}],
            'trace_rows': [{'trace_id': 'trace-1', 'event_id': 'evt-1'}],
            'metrics_rows': [{'snapshot_id': 'snap-1'}],
            'export_manifest': {'scope': {'tenant_id': 'tenant-a'}},
            'causal_chain': {
                'budget_guard': {'event_id': 'evt-1', 'status': 'denied'},
                'execution': {'event_id': 'evt-1', 'status': 'executed'},
                'verification': {'event_id': 'evt-1', 'status': 'verified'},
                'revenue': {'event_id': 'evt-1', 'trace_id': 'trace-1'},
                'memory': {'memory_key': 'evt-2'},
            },
        }
    )
    assert verdict.valid is False
    assert 'causal_chain_budget_guard_bypass' in verdict.violations
    assert 'causal_chain_memory_unanchored' in verdict.violations


def test_scope_lineage_guard_classifies_profile_drift_as_quarantine() -> None:
    verdict = EconomicScopeLineageGuard().validate(
        current_scope={'tenant_id': 'tenant-a', 'business_id': 'biz-a', 'profile_name': 'standard'},
        incoming_scope={'tenant_id': 'tenant-a', 'business_id': 'biz-a', 'profile_name': 'regulated'},
        declared_lineage=None,
    )
    assert verdict.migration_allowed is False
    assert verdict.decision_class == 'quarantine'


def test_import_denies_poisoned_digest_reimport(tmp_path: Path) -> None:
    quarantine = InMemoryEconomicBundleQuarantineStore()
    service = EconomicAuditBundleService(quarantine_sink=quarantine)
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
    raw['payload']['export_manifest']['manifest_digest'] = 'corrupt'
    path.write_text(json.dumps(raw), encoding='utf-8')

    with pytest.raises(ValueError, match='economic bundle validation failed'):
        service.restore_bundle(bundle_path=path, strict_validation=True, expected_scope=scope, expected_profile_name='standard')

    rows = quarantine.list_rows()
    assert rows
    assert rows[-1].status == 'denied'
    assert rows[-1].poisoned is True

    with pytest.raises(ValueError, match='poisoned digest'):
        service.restore_bundle(bundle_path=path, strict_validation=True, expected_scope=scope, expected_profile_name='standard')


def test_backend_authority_resolver_respects_quarantine_and_advisory_roles() -> None:
    verdict = EconomicBackendAuthorityResolver().build(
        backend_views=[
            {'backend_name': 'primary', 'snapshot_count': 4, 'trace_count': 4, 'feedback_count': 4, 'roi_count': 4, 'metrics_count': 1},
            {'backend_name': 'advisory-node', 'backend_role': 'advisory', 'snapshot_count': 10, 'trace_count': 1, 'feedback_count': 1, 'roi_count': 1, 'metrics_count': 50},
            {'backend_name': 'corrupt-node', 'corrupted': True, 'snapshot_count': 20},
        ]
    )
    assert verdict.authoritative_backend == 'primary'
    assert 'advisory-node' in verdict.advisory_backends
    assert 'corrupt-node' in verdict.quarantined_backends


def test_split_brain_guard_emits_handoff_markers() -> None:
    verdict = EconomicSplitBrainGuard().build(
        node_views=[
            {'node_id': 'node-a', 'leader_epoch': 1, 'fencing_token': '1', 'active': True, 'store_digest': 'x'},
            {'node_id': 'node-b', 'leader_epoch': 2, 'fencing_token': '2', 'active': True, 'store_digest': 'y'},
        ]
    )
    assert verdict.authoritative_node_id == 'node-b'
    assert verdict.winner_confirmation_marker.startswith('economic-winner::node-b')
    assert verdict.stale_node_demotions['node-a'].startswith('economic-stale-demotion::node-a')
    assert verdict.replay_refusal_markers['node-a'].startswith('economic-replay-refusal::node-a')
