from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.safety.controls.boot_integrity import SafetyBootIntegrityChecker
from core.safety.controls.key_registry import SafetyKeyRegistry
from core.safety.controls.multi_step_approval.models import ApprovalTicket
from core.safety.controls.multi_step_approval.repository import SqliteApprovalRepository
from core.safety.controls.policy_manifest import PolicyManifestSigner
from core.safety.controls.policy_trust_chain import PolicyTrustChain
from core.safety.controls.rollback_engine.models import RollbackPlan
from core.safety.controls.rollback_engine.store import SqliteRollbackPlanStore
from core.safety.controls.simulation_gate.evidence import SimulationEvidenceVerifier


def test_key_registry_supports_json_rotation_config(monkeypatch) -> None:
    monkeypatch.setenv('BUSINESAIOS_SAFETY_SIGNING_KEYS_JSON', json.dumps({'keys': [{'key_id': 'current', 'secret': 's1', 'active': True}, {'key_id': 'next', 'secret': 's2', 'active': False}]}))
    monkeypatch.setenv('BUSINESAIOS_SAFETY_ACTIVE_KEY_ID', 'current')
    monkeypatch.setenv('BUSINESAIOS_SAFETY_NEXT_KEY_ID', 'next')
    reg = SafetyKeyRegistry()
    assert reg.current.key_id == 'current'
    assert reg.next_key is not None and reg.next_key.key_id == 'next'


def test_boot_integrity_strict_rejects_insecure_simulation_secret(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv('BUSINESAIOS_SAFETY_SIGNING_SECRET', 'safe-policy-secret')
    monkeypatch.setenv('BUSINESAIOS_SAFETY_SIGNING_KEY_ID', 'primary')
    monkeypatch.delenv('BUSINESAIOS_SIMULATION_EVIDENCE_SECRET', raising=False)
    chain = PolicyTrustChain(path=str(tmp_path / 'chain.jsonl'), snapshot_path=str(tmp_path / 'snap.jsonl'))
    signer = PolicyManifestSigner()
    report = SafetyBootIntegrityChecker().verify(manifest_signer=signer, trust_chain=chain, strict=True)
    assert report.healthy is False
    assert 'unsafe_simulation_evidence_signing_fallback' in report.failures


def test_policy_trust_chain_detects_snapshot_tampering(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv('BUSINESAIOS_SAFETY_SIGNING_SECRET', 'safe-policy-secret')
    signer = PolicyManifestSigner()
    chain_path = tmp_path / 'chain.jsonl'
    snapshot_path = tmp_path / 'snapshot.jsonl'
    chain = PolicyTrustChain(path=str(chain_path), snapshot_path=str(snapshot_path))
    manifest = signer.build(tenant_id='t-223', policy_scope='scope', policy_payload={'x': 1})
    chain.append(manifest)
    lines = snapshot_path.read_text(encoding='utf-8').splitlines()
    data = json.loads(lines[-1])
    data['record_count'] = 999
    lines[-1] = json.dumps(data, sort_keys=True)
    snapshot_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    reloaded = PolicyTrustChain(path=str(chain_path), snapshot_path=str(snapshot_path))
    assert reloaded.verify_all() is False


def test_sqlite_approval_repository_rejects_stale_fencing_token(tmp_path: Path) -> None:
    repo = SqliteApprovalRepository(sqlite_path=str(tmp_path / 'approval.sqlite3'))
    repo.put(ApprovalTicket(action_id='ap-223'))
    leased = repo.acquire_lease(action_id='ap-223', owner='worker-a')
    assert leased is not None
    current = repo.get('ap-223')
    with pytest.raises(RuntimeError, match='approval_ticket_stale_fencing_token'):
        repo.compare_and_set(expected_version=current.version, ticket=ApprovalTicket(action_id='ap-223', lease_owner='worker-b', fencing_token=0, version=current.version))


def test_sqlite_rollback_store_rejects_stale_fencing_token(tmp_path: Path) -> None:
    store = SqliteRollbackPlanStore(sqlite_path=str(tmp_path / 'rollback.sqlite3'))
    store.put(tenant_id='t-223', action_id='rb-223', plan=RollbackPlan(source_action='deploy'))
    leased = store.acquire_lease(tenant_id='t-223', action_id='rb-223', owner='worker-a')
    assert leased is not None
    current = store.get(tenant_id='t-223', action_id='rb-223')
    assert current is not None
    with pytest.raises(RuntimeError, match='rollback_plan_stale_fencing_token'):
        store.compare_and_set(tenant_id='t-223', action_id='rb-223', expected_version=current.version, plan=RollbackPlan(source_action='deploy', lease_owner='worker-b', fencing_token=0, version=current.version))


def test_simulation_evidence_signs_dataset_fingerprint() -> None:
    from core.safety.controls.action_context import SafetyActionContext
    verifier = SimulationEvidenceVerifier(secret='wave223-secret')
    ctx = SafetyActionContext(action='pricing.publish_offer', tenant_id='tenant-223', user_id=None, payload={'tenant_id': 'tenant-223', 'simulation_dataset_fingerprint': 'dataset-v1'})
    sig = verifier.sign(ctx=ctx, score=0.9, provenance='sim', model_fingerprint='model-v3', expires_at='2999-01-01T00:00:00+00:00')
    payload = {
        'tenant_id': 'tenant-223',
        'simulation_required': True,
        'simulation_score': 0.9,
        'simulation_verified': True,
        'simulation_provenance': 'sim',
        'simulation_signature': sig,
        'simulation_model_fingerprint': 'model-v3',
        'simulation_expires_at': '2999-01-01T00:00:00+00:00',
        'simulation_dataset_fingerprint': verifier.dataset_fingerprint(ctx),
    }
    evidence = verifier.from_payload(SafetyActionContext(action='pricing.publish_offer', tenant_id='tenant-223', user_id=None, payload=payload))
    assert evidence.verified is True
