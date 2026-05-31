from __future__ import annotations

import json
from pathlib import Path

import pytest

from execution.economic_audit_bundle import EconomicAuditBundleService
from execution.economic_bundle_quarantine_store import InMemoryEconomicBundleQuarantineStore


def _scope() -> dict[str, str]:
    return {
        'tenant_id': 'tenant-a',
        'business_id': 'biz-a',
        'tenant_tier': 'standard',
        'business_tier': 'standard',
        'profile_name': 'standard',
    }


def _build_bundle(service: EconomicAuditBundleService, *, index: int):
    scope = _scope()
    manifest = service.build_export_manifest(stores={}, node_id=f'node-{index}', scope=scope)
    return service.build_bundle(
        bundle_id=f'bundle-{index}',
        feedback_rows=[{'event_id': f'evt-{index}'}],
        roi_rows=[{'event_id': f'evt-{index}'}],
        snapshot_rows=[{'snapshot_id': f'snap-{index}'}],
        trace_rows=[{'trace_id': f'trace-{index}', 'event_id': f'evt-{index}'}],
        metrics_rows=[{'snapshot_id': f'snap-{index}'}],
        audit_summary={'restart_resume_consistent': True},
        export_manifest=manifest,
        scope_profile=scope,
    )


def test_long_replay_chain_strict_restore_survives_multiple_generations(tmp_path: Path) -> None:
    service = EconomicAuditBundleService(quarantine_sink=InMemoryEconomicBundleQuarantineStore())
    expected_scope = _scope()
    for index in range(1, 8):
        path = tmp_path / f'bundle-{index}.json'
        bundle = _build_bundle(service, index=index)
        service.export_json(bundle=bundle, path=path)
        restored = service.restore_bundle(
            bundle_path=path,
            strict_validation=True,
            expected_scope=expected_scope,
            expected_profile_name='standard',
        )
        assert restored['bundle_id'] == f'bundle-{index}'
        assert restored['payload']['feedback_rows'][0]['event_id'] == f'evt-{index}'


def test_mixed_corruption_marks_poisoned_digest_and_blocks_retry(tmp_path: Path) -> None:
    quarantine = InMemoryEconomicBundleQuarantineStore()
    service = EconomicAuditBundleService(quarantine_sink=quarantine)
    bundle = _build_bundle(service, index=1)
    path = tmp_path / 'corrupt-bundle.json'
    service.export_json(bundle=bundle, path=path)

    raw = json.loads(path.read_text(encoding='utf-8'))
    raw['payload']['feedback_rows'] = [{'event_id': 'evt-1'}]
    raw['payload']['trace_rows'] = []
    raw['payload']['export_manifest']['scope_lineage'] = {'old_scope': {'tenant_id': 'tenant-x'}, 'new_scope': {'tenant_id': 'tenant-y'}}
    raw['payload']['metadata']['scope_profile']['tenant_id'] = 'tenant-z'
    path.write_text(json.dumps(raw), encoding='utf-8')

    with pytest.raises(ValueError, match='economic bundle validation failed'):
        service.restore_bundle(
            bundle_path=path,
            strict_validation=True,
            expected_scope=_scope(),
            expected_profile_name='standard',
        )

    rows = quarantine.list_rows()
    assert rows[-1].status == 'denied'
    assert rows[-1].poisoned is True

    with pytest.raises(ValueError, match='poisoned digest'):
        service.restore_bundle(
            bundle_path=path,
            strict_validation=True,
            expected_scope=_scope(),
            expected_profile_name='standard',
        )



def test_cross_version_bundle_restore_is_denied_even_with_valid_shape(tmp_path: Path) -> None:
    quarantine = InMemoryEconomicBundleQuarantineStore()
    service = EconomicAuditBundleService(quarantine_sink=quarantine)
    bundle = _build_bundle(service, index=8)
    path = tmp_path / 'bundle-cross-version.json'
    service.export_json(bundle=bundle, path=path)

    raw = json.loads(path.read_text(encoding='utf-8'))
    raw['payload']['export_manifest']['bundle_schema_version'] = '3'
    raw['payload']['export_manifest']['manifest_digest'] = 'tampered'
    path.write_text(json.dumps(raw), encoding='utf-8')

    with pytest.raises(ValueError, match='economic bundle validation failed'):
        service.restore_bundle(
            bundle_path=path,
            strict_validation=True,
            expected_scope=_scope(),
            expected_profile_name='standard',
        )

    rows = quarantine.list_rows()
    assert rows[-1].status == 'denied'
    assert rows[-1].poisoned is True


def test_partial_progress_restart_matrix_rejects_second_resume_after_corruption(tmp_path: Path) -> None:
    quarantine = InMemoryEconomicBundleQuarantineStore()
    service = EconomicAuditBundleService(quarantine_sink=quarantine)
    bundle = _build_bundle(service, index=9)
    path = tmp_path / 'bundle-partial-progress.json'
    service.export_json(bundle=bundle, path=path)

    raw = json.loads(path.read_text(encoding='utf-8'))
    raw['payload']['metadata']['replay_epoch'] = 'epoch-9'
    raw['payload']['metadata']['resume_token'] = 'resume-1'
    raw['payload']['metadata']['restore_status'] = 'in_progress'
    path.write_text(json.dumps(raw), encoding='utf-8')

    restored = service.restore_bundle(
        bundle_path=path,
        strict_validation=False,
        expected_scope=_scope(),
        expected_profile_name='standard',
    )
    assert restored['payload']['metadata']['resume_token'] == 'resume-1'

    raw = json.loads(path.read_text(encoding='utf-8'))
    raw['payload']['metadata']['resume_token'] = 'resume-2'
    raw['digest'] = 'poisoned-digest'
    path.write_text(json.dumps(raw), encoding='utf-8')

    with pytest.raises(ValueError, match='economic bundle validation failed'):
        service.restore_bundle(
            bundle_path=path,
            strict_validation=True,
            expected_scope=_scope(),
            expected_profile_name='standard',
        )

    rows = quarantine.list_rows()
    assert rows[-1].status == 'denied'


from execution.economic_replay_epoch_guard import EconomicReplayEpochGuard


def test_scope_lineage_digest_mismatch_is_denied_even_when_manifest_shape_is_valid(tmp_path: Path) -> None:
    quarantine = InMemoryEconomicBundleQuarantineStore()
    service = EconomicAuditBundleService(quarantine_sink=quarantine)
    bundle = _build_bundle(service, index=10)
    path = tmp_path / 'bundle-lineage-digest-mismatch.json'
    service.export_json(bundle=bundle, path=path)

    raw = json.loads(path.read_text(encoding='utf-8'))
    manifest = raw['payload']['export_manifest']
    manifest['scope_lineage'] = {
        'old_scope': {'tenant_id': 'tenant-a', 'business_id': 'biz-a', 'tenant_tier': 'standard', 'business_tier': 'standard'},
        'new_scope': {'tenant_id': 'tenant-a', 'business_id': 'biz-a', 'tenant_tier': 'standard', 'business_tier': 'standard'},
        'mode': 'migration',
    }
    manifest['scope_lineage_digest'] = 'tampered-lineage-digest'
    manifest['manifest_digest'] = 'tampered-manifest-digest'
    path.write_text(json.dumps(raw), encoding='utf-8')

    with pytest.raises(ValueError, match='economic bundle validation failed'):
        service.restore_bundle(
            bundle_path=path,
            strict_validation=True,
            expected_scope=_scope(),
            expected_profile_name='standard',
        )

    assert quarantine.list_rows()[-1].status == 'denied'


def test_replay_epoch_guard_rejects_depth_gap_and_anchor_mismatch() -> None:
    guard = EconomicReplayEpochGuard()
    gap_verdict = guard.validate(
        current_state={'meta': {'economic_replay_epoch': 'epoch-1', 'economic_replay_anchor': 'anchor-1'}},
        incoming_payload={'metadata': {'replay_epoch': 'epoch-1', 'parent_replay_epoch': 'epoch-0', 'replay_chain_depth': 3, 'replay_history': ['epoch-0', 'epoch-1'], 'replay_anchor': 'anchor-1'}},
    )
    assert gap_verdict.accepted is False
    assert gap_verdict.reason == 'economic_replay_gap_detected'

    anchor_verdict = guard.validate(
        current_state={'meta': {'economic_replay_epoch': 'epoch-1', 'economic_replay_anchor': 'anchor-1'}},
        incoming_payload={'metadata': {'replay_epoch': 'epoch-1', 'parent_replay_epoch': 'epoch-0', 'replay_chain_depth': 1, 'replay_history': ['epoch-0'], 'replay_anchor': 'anchor-2'}},
    )
    assert anchor_verdict.accepted is False
    assert anchor_verdict.reason == 'economic_replay_anchor_mismatch'


def test_replay_epoch_guard_rejects_orphan_and_branching_chain() -> None:
    guard = EconomicReplayEpochGuard()
    orphan = guard.validate(
        current_state={'meta': {}},
        incoming_payload={'metadata': {'replay_epoch': 'epoch-2', 'replay_chain_depth': 1, 'replay_anchor': 'anchor-2'}},
    )
    assert orphan.accepted is False
    assert orphan.reason == 'economic_replay_orphan_chain'

    branch = guard.validate(
        current_state={'meta': {}},
        incoming_payload={'metadata': {'replay_epoch': 'epoch-2', 'parent_replay_epoch': 'epoch-1', 'replay_chain_depth': 2, 'replay_history': ['epoch-1', 'epoch-1'], 'replay_anchor': 'anchor-2'}},
    )
    assert branch.accepted is False
    assert branch.reason == 'economic_replay_branching_detected'



def test_payload_valid_but_lineage_and_semantic_corruption_are_denied(tmp_path: Path) -> None:
    quarantine = InMemoryEconomicBundleQuarantineStore()
    service = EconomicAuditBundleService(quarantine_sink=quarantine)
    bundle = _build_bundle(service, index=11)
    path = tmp_path / 'bundle-corruption-combinatorics.json'
    service.export_json(bundle=bundle, path=path)

    raw = json.loads(path.read_text(encoding='utf-8'))
    payload = raw['payload']
    payload['export_manifest']['scope_lineage'] = {
        'old_scope': {'tenant_id': 'tenant-x', 'business_id': 'biz-a', 'tenant_tier': 'standard', 'business_tier': 'standard'},
        'new_scope': {'tenant_id': 'tenant-y', 'business_id': 'biz-a', 'tenant_tier': 'standard', 'business_tier': 'standard'},
        'mode': 'migration',
    }
    payload['trace_rows'] = []
    raw['digest'] = __import__('hashlib').sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    path.write_text(json.dumps(raw), encoding='utf-8')

    with pytest.raises(ValueError, match='economic bundle validation failed'):
        service.restore_bundle(
            bundle_path=path,
            strict_validation=True,
            expected_scope=_scope(),
            expected_profile_name='standard',
        )

    rows = quarantine.list_rows()
    assert rows[-1].status in {'quarantined', 'denied'}

    _ = service.import_json
    # Re-read failure details through direct validator path to prove combinatorics were detected.
    data = json.loads(path.read_text(encoding='utf-8'))
    from execution.economic_audit_bundle import validate_economic_bundle_payload
    verdict = validate_economic_bundle_payload(
        bundle=data,
        expected_scope=_scope(),
        expected_profile_name='standard',
    )
    assert 'schema_valid_semantic_corruption' in verdict['issues']
    assert any(issue in verdict['issues'] for issue in ('manifest_valid_lineage_invalid', 'payload_valid_scope_lineage_invalid', 'payload_valid_lineage_digest_conflict'))
