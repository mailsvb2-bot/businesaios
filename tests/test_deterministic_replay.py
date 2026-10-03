from types import SimpleNamespace

import pytest

from contracts.world_model_semantics import (
    WorldModelSemanticRecordV1,
    WorldModelSemanticViewV1,
)
from core.ai.decision import Decision
from core.ai.decision_archive import MemoryDecisionArchive
from core.ai.snapshot_store import MemorySnapshotStore
from core.security.keyring import Keyring
from core.utils.canonical import sha256_hex
from kernel.decision_crypto import signed_envelope_from_decision
from kernel.world_state import WorldStateV1
from runtime.replay import HistoricalReplayEngine, ReplayEngine


class ReplayCandidate:
    __module__ = "core.policies.phase15_replay_fixture"
    id = "candidate@v2"

    def propose(self, state):
        return SimpleNamespace(
            action="send_message@v1",
            payload={
                "expected_reward": float(state.economy.get("expected_reward") or 0.0),
                "expected_cost": 2.0,
                "risk_score": 0.1,
            },
        )


class ReplayRegistry:
    def __init__(self, candidate) -> None:
        self._candidate = candidate

    def maybe_get(self, candidate_policy_id: str):
        candidate = self._candidate
        return (
            candidate
            if candidate is not None
            and str(getattr(candidate, "id", "")) == str(candidate_policy_id)
            else None
        )


def _historical_engine(archive, snapshots, keyring, candidate):
    return HistoricalReplayEngine(
        archive,
        snapshots,
        keyring=keyring,
        policy_registry=ReplayRegistry(candidate),
    )


def test_deterministic_replay():
    archive = MemoryDecisionArchive()
    engine = ReplayEngine(archive)

    # Store a bit-exact envelope and replay it.
    from core.ai.decision import DecisionEnvelope

    env = DecisionEnvelope(
        decision=Decision(
            decision_id="decision_1",
            issuer_id="businesaios-core",
            issued_at_ms=1,
            expires_at_ms=2,
            policy_id="p",
            action="send_message@v1",
            payload={"user_id": "u", "text": "hi"},
            snapshot_id="s",
            state_hash="h",
            correlation_id="c",
            state_schema_version=1,
            action_schema_version=1,
            envelope_version=1,
        ),
        payload_hash="ph",
        signature="sig",
        kid="k1",
        envelope_version=1,
    )

    archive.put(env)

    d1 = engine.replay("decision_1")
    d2 = engine.replay("decision_1")
    assert d1 == d2


def _historical_fixture(*, state_timestamp_ms: int = 100):
    state = WorldStateV1(
        schema_version=1,
        user={"user_id": "u-1"},
        session={"channel": "test"},
        product={"product_id": "p-1", "business_id": "b-1"},
        economy={"expected_reward": 3.0},
        timestamp_ms=state_timestamp_ms,
        tenant_id="t-1",
        user_id="u-1",
    )
    state_bytes = state.canonical_bytes()
    decision = Decision(
        decision_id="decision-historical",
        issuer_id="businesaios-core",
        issued_at_ms=200,
        expires_at_ms=300,
        policy_id="active@v1",
        action="noop@v1",
        payload={
            "tenant_id": "t-1",
            "business_id": "b-1",
            "actor_id": "u-1",
            "expected_cost": 1.0,
        },
        snapshot_id="snapshot-historical",
        state_hash=sha256_hex(state_bytes),
        correlation_id="correlation-historical",
        state_schema_version=1,
        action_schema_version=1,
        envelope_version=1,
    )
    keyring = Keyring({"k1": {"secret": b"s1", "revoked": False}}, "k1")
    env = signed_envelope_from_decision(decision=decision, keyring=keyring)
    archive = MemoryDecisionArchive()
    archive.put(env)
    snapshots = MemorySnapshotStore()
    snapshots.put(decision.snapshot_id, state_bytes)
    return state, env, archive, snapshots, keyring


def test_historical_replay_uses_exact_signed_decision_snapshot() -> None:
    state, env, archive, snapshots, keyring = _historical_fixture()
    candidate = ReplayCandidate()
    result = _historical_engine(archive, snapshots, keyring, candidate).replay_challenger(
        env.decision.decision_id,
        candidate.id,
    )

    assert result["historical_replay"] is True
    assert result["historical_source"] == "decision_snapshot"
    assert result["future_leakage"] is False
    assert result["external_effect"] is False
    assert result["writes_outbox"] is False
    assert result["context_match"] is True
    assert result["state_hash"] == env.decision.state_hash
    assert result["snapshot_id"] == env.decision.snapshot_id
    assert result["historical_state_timestamp_ms"] == state.timestamp_ms
    assert result["candidate_action"] == "send_message@v1"


def test_historical_replay_rejects_tampered_snapshot() -> None:
    _state, env, archive, snapshots, keyring = _historical_fixture()
    snapshots.put(env.decision.snapshot_id, b'{"tampered":true}')
    candidate = ReplayCandidate()

    with pytest.raises(RuntimeError, match="HISTORICAL_REPLAY_SNAPSHOT_HASH_MISMATCH"):
        _historical_engine(archive, snapshots, keyring, candidate).replay_challenger(
            env.decision.decision_id,
            candidate.id,
        )


def test_historical_replay_rejects_future_state() -> None:
    state = WorldStateV1(
        schema_version=1,
        user={"user_id": "u-1"},
        session={},
        product={"business_id": "b-1"},
        economy={},
        timestamp_ms=201,
        tenant_id="t-1",
        user_id="u-1",
    )
    state_bytes = state.canonical_bytes()
    decision = Decision(
        decision_id="decision-future",
        issuer_id="businesaios-core",
        issued_at_ms=200,
        expires_at_ms=300,
        policy_id="active@v1",
        action="noop@v1",
        payload={"tenant_id": "t-1", "business_id": "b-1"},
        snapshot_id="snapshot-future",
        state_hash=sha256_hex(state_bytes),
        correlation_id="correlation-future",
        state_schema_version=1,
        action_schema_version=1,
        envelope_version=1,
    )
    keyring = Keyring({"k1": {"secret": b"s1", "revoked": False}}, "k1")
    archive = MemoryDecisionArchive()
    archive.put(signed_envelope_from_decision(decision=decision, keyring=keyring))
    snapshots = MemorySnapshotStore()
    snapshots.put(decision.snapshot_id, state_bytes)

    candidate = ReplayCandidate()
    with pytest.raises(RuntimeError, match="HISTORICAL_REPLAY_FUTURE_STATE"):
        _historical_engine(archive, snapshots, keyring, candidate).replay_challenger(
            decision.decision_id,
            candidate.id,
        )


def test_historical_replay_rejects_noncanonical_candidate() -> None:
    _state, env, archive, snapshots, keyring = _historical_fixture()

    class ForeignCandidate:
        id = "foreign@v1"

    foreign = ForeignCandidate()
    with pytest.raises(ValueError, match="HISTORICAL_REPLAY_CANDIDATE_NOT_CANONICAL"):
        _historical_engine(archive, snapshots, keyring, foreign).replay_challenger(
            env.decision.decision_id,
            foreign.id,
        )


def test_historical_replay_rejects_future_semantic_observation() -> None:
    record = WorldModelSemanticRecordV1(
        record_id="record-1",
        tenant_id="t-1",
        business_id="b-1",
        epistemic_type="fact",
        key="revenue",
        value=10,
        source="test",
        occurred_at_ms=100,
        observed_at_ms=201,
        recorded_at_ms=201,
        confidence=1.0,
        authoritative=True,
        provenance_hash="proof",
    )
    semantics = WorldModelSemanticViewV1(
        state_id="state-1",
        tenant_id="t-1",
        business_id="b-1",
        generated_at_ms=150,
        records=(record,),
    )
    state = WorldStateV1(
        schema_version=1,
        user={"user_id": "u-1"},
        session={},
        product={"business_id": "b-1"},
        economy={},
        timestamp_ms=100,
        tenant_id="t-1",
        user_id="u-1",
        world_model_semantics=semantics,
    )
    state_bytes = state.canonical_bytes()
    decision = Decision(
        decision_id="decision-future-semantic",
        issuer_id="businesaios-core",
        issued_at_ms=200,
        expires_at_ms=300,
        policy_id="active@v1",
        action="noop@v1",
        payload={"tenant_id": "t-1", "business_id": "b-1"},
        snapshot_id="snapshot-future-semantic",
        state_hash=sha256_hex(state_bytes),
        correlation_id="correlation-future-semantic",
        state_schema_version=1,
        action_schema_version=1,
        envelope_version=1,
    )
    keyring = Keyring({"k1": {"secret": b"s1", "revoked": False}}, "k1")
    archive = MemoryDecisionArchive()
    archive.put(signed_envelope_from_decision(decision=decision, keyring=keyring))
    snapshots = MemorySnapshotStore()
    snapshots.put(decision.snapshot_id, state_bytes)
    candidate = ReplayCandidate()

    with pytest.raises(RuntimeError, match="HISTORICAL_REPLAY_FUTURE_STATE"):
        _historical_engine(archive, snapshots, keyring, candidate).replay_challenger(
            decision.decision_id,
            candidate.id,
        )


def test_historical_replay_rejects_state_hash_tampering_even_with_matching_snapshot() -> None:
    state, env, archive, snapshots, keyring = _historical_fixture()
    tampered_state = WorldStateV1(
        schema_version=state.schema_version,
        user=dict(state.user),
        session=dict(state.session),
        product=dict(state.product),
        economy={"expected_reward": 999.0},
        timestamp_ms=state.timestamp_ms,
        tenant_id=state.tenant_id,
        meta=dict(state.meta),
        user_id=state.user_id,
        safe_mode=state.safe_mode,
        capital=state.capital,
        horizon_state=state.horizon_state,
        behavior=state.behavior,
        price_constraints=state.price_constraints,
        deployment_proposal=state.deployment_proposal,
        manual_override=state.manual_override,
        world_model_semantics=state.world_model_semantics,
    )
    tampered_bytes = tampered_state.canonical_bytes()
    tampered_decision = Decision(
        **{
            **dict(env.decision.__dict__),
            "state_hash": sha256_hex(tampered_bytes),
        }
    )
    from core.ai.decision import DecisionEnvelope

    archive.put(
        DecisionEnvelope(
            decision=tampered_decision,
            payload_hash=env.payload_hash,
            signature=env.signature,
            kid=env.kid,
            envelope_version=env.envelope_version,
        )
    )
    snapshots.put(tampered_decision.snapshot_id, tampered_bytes)
    candidate = ReplayCandidate()

    with pytest.raises(RuntimeError, match="HISTORICAL_REPLAY_SIGNATURE_INVALID"):
        _historical_engine(archive, snapshots, keyring, candidate).replay_challenger(
            tampered_decision.decision_id,
            candidate.id,
        )


def test_historical_replay_rejects_unregistered_candidate_id() -> None:
    _state, env, archive, snapshots, keyring = _historical_fixture()
    engine = HistoricalReplayEngine(
        archive,
        snapshots,
        keyring=keyring,
        policy_registry=ReplayRegistry(None),
    )

    with pytest.raises(ValueError, match="HISTORICAL_REPLAY_CANDIDATE_NOT_REGISTERED"):
        engine.replay_challenger(env.decision.decision_id, "candidate@missing")
