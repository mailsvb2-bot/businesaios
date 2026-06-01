from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.safety_control_boot import build_safety_control_runtime
from core.safety.controls.action_context import SafetyActionContext
from core.safety.controls.key_registry import SafetyKeyRegistry
from core.safety.controls.multi_step_approval.models import ApprovalTicket
from core.safety.controls.multi_step_approval.repository import SqliteApprovalRepository
from core.safety.controls.policy_manifest import PolicyManifestSigner
from core.safety.controls.policy_trust_chain import PolicyTrustChain
from core.safety.controls.rollback_engine.models import RollbackPlan
from core.safety.controls.rollback_engine.store import SqliteRollbackPlanStore
from core.safety.controls.simulation_gate.evidence import SimulationEvidence, SimulationEvidenceVerifier
from core.safety.controls.simulation_gate.models import SimulationGatePolicy
from core.safety.controls.simulation_gate.service import SimulationGate


def test_strict_boot_rejects_insecure_default_key(monkeypatch) -> None:
    monkeypatch.setenv('BUSINESAIOS_SAFETY_BOOT_STRICT', '1')
    monkeypatch.delenv('BUSINESAIOS_SAFETY_SIGNING_KEYS', raising=False)
    monkeypatch.delenv('BUSINESAIOS_SAFETY_SIGNING_SECRET', raising=False)
    build_safety_control_runtime.cache_clear()
    with pytest.raises(ValueError, match='safety boot integrity check failed'):
        build_safety_control_runtime(persistent=False)


def test_policy_trust_chain_detects_history_truncation(tmp_path: Path) -> None:
    registry = SafetyKeyRegistry()
    signer = PolicyManifestSigner(key_registry=registry)
    chain_path = tmp_path / 'chain.jsonl'
    snapshot_path = tmp_path / 'snapshot.jsonl'
    chain = PolicyTrustChain(path=str(chain_path), snapshot_path=str(snapshot_path))
    manifest = signer.build(tenant_id='t-1', policy_scope='safety_profile', policy_payload={'mode': 'strict'})
    chain.append(manifest)
    chain_path.write_text('', encoding='utf-8')
    reloaded = PolicyTrustChain(path=str(chain_path), snapshot_path=str(snapshot_path))
    assert reloaded.verify_all() is False


def test_simulation_gate_rejects_expired_signed_artifact() -> None:
    verifier = SimulationEvidenceVerifier(secret='wave222-secret')
    ctx = SafetyActionContext(action='pricing.publish_offer', tenant_id='tenant-222', user_id=None, payload={'tenant_id': 'tenant-222', 'approval_required': True})
    evidence = SimulationEvidence(
        score=0.99,
        provenance='simulator:v2',
        verified=True,
        artifact_fingerprint=verifier.payload_fingerprint(ctx),
        model_fingerprint='model-v2',
        expires_at='2000-01-01T00:00:00+00:00',
    )
    signature = verifier.sign(
        ctx=ctx,
        score=evidence.score,
        provenance=evidence.provenance,
        artifact_fingerprint=evidence.artifact_fingerprint,
        model_fingerprint=evidence.model_fingerprint,
        expires_at=evidence.expires_at,
    )
    payload = {
        'tenant_id': 'tenant-222',
        'simulation_required': True,
        'simulation_score': evidence.score,
        'simulation_verified': True,
        'simulation_provenance': evidence.provenance,
        'simulation_signature': signature,
        'simulation_artifact_fingerprint': evidence.artifact_fingerprint,
        'simulation_model_fingerprint': evidence.model_fingerprint,
        'simulation_expires_at': evidence.expires_at,
    }
    gate = SimulationGate(SimulationGatePolicy(required_for_prefixes=('pricing.',), min_score=0.8), evidence_verifier=verifier)
    decision = gate.evaluate(SafetyActionContext(action='pricing.publish_offer', tenant_id='tenant-222', user_id=None, payload=payload))
    assert str(decision.status.value) == 'block'


def test_sqlite_approval_repository_compare_and_set_detects_conflict(tmp_path: Path) -> None:
    repo = SqliteApprovalRepository(sqlite_path=str(tmp_path / 'approval.sqlite3'))
    repo.put(ApprovalTicket(action_id='ap-222'))
    current = repo.get('ap-222')
    repo.compare_and_set(expected_version=current.version, ticket=ApprovalTicket(action_id='ap-222', approvals=('alice',), version=current.version))
    with pytest.raises(RuntimeError, match='approval_ticket_version_conflict'):
        repo.compare_and_set(expected_version=current.version, ticket=ApprovalTicket(action_id='ap-222', approvals=('alice', 'bob'), version=current.version))


def test_sqlite_rollback_store_compare_and_set_detects_conflict(tmp_path: Path) -> None:
    store = SqliteRollbackPlanStore(sqlite_path=str(tmp_path / 'rollback.sqlite3'))
    store.put(tenant_id='tenant-222', action_id='rb-1', plan=RollbackPlan(source_action='deploy'))
    current = store.get(tenant_id='tenant-222', action_id='rb-1')
    assert current is not None
    store.compare_and_set(tenant_id='tenant-222', action_id='rb-1', expected_version=current.version, plan=RollbackPlan(source_action='deploy', version=current.version, lease_owner='worker-a'))
    with pytest.raises(RuntimeError, match='rollback_plan_version_conflict'):
        store.compare_and_set(tenant_id='tenant-222', action_id='rb-1', expected_version=current.version, plan=RollbackPlan(source_action='deploy', version=current.version, lease_owner='worker-b'))
