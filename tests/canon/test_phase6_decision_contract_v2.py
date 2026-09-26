from __future__ import annotations

import base64
import hashlib
import hmac

import pytest

from application.decision_runtime.flow import build_envelope
from contracts.decisioning.sovereign_decision_contract import Decision, DecisionContractV2
from core.ai.decision_core import _decision_envelope_version
from core.security.keyring import Keyring
from core.utils.canonical import canonical_json_bytes, payload_hash
from kernel.decision_crypto import (
    canonical_signed_payload,
    sign_decision,
    signed_envelope_from_decision,
    verify_signed_material,
)
from observability.platform.decision_archive.sqlite_decision_archive import SqliteDecisionArchive


def _decision(*, envelope_version: int, contract_v2: dict | None = None) -> Decision:
    return Decision(
        decision_id="decision-1",
        issuer_id="businesaios-core",
        issued_at_ms=1000,
        expires_at_ms=2000,
        policy_id="policy-1",
        action="send_message@v1",
        payload={"tenant_id": "tenant-1", "text": "hello"},
        snapshot_id="snapshot-1",
        state_hash="state-hash-1",
        correlation_id="correlation-1",
        state_schema_version=1,
        action_schema_version=1,
        envelope_version=envelope_version,
        contract_v2=contract_v2,
    )


def _contract() -> dict:
    return DecisionContractV2(
        business_id="business-1",
        goal_id="goal-1",
        world_state_version="state-42",
        agent_id="businesaios-core",
        model_profile="UNKNOWN",
        decision_strategy="policy-1",
        alternatives=(
            {"option_id": "send_message@v1", "score": 2.0, "reason": "ranked"},
            {"option_id": "noop@v1", "score": 0.0, "reason": "baseline"},
        ),
        selected_option={"option_id": "send_message@v1", "score": 2.0},
        rationale={
            "evidence": ["evidence-1"],
            "constraints": ["quiet_hours"],
            "alternatives": ["send_message@v1", "noop@v1"],
            "selection_reason": "ranked",
            "uncertainties": ["confidence:UNKNOWN"],
            "expected_outcome": None,
            "risk": None,
        },
        confidence=None,
        expected_value=None,
        risk=None,
        created_at=1000,
        do_nothing_baseline=None,
    ).as_dict()


def test_v1_signed_surface_is_byte_compatible_with_historical_shape() -> None:
    decision = _decision(envelope_version=1)
    surface = canonical_signed_payload(
        decision=decision,
        payload_hash_value=payload_hash(decision.payload),
        kid="k1",
    )
    expected = {
        "envelope_version": 1,
        "decision_id": "decision-1",
        "issuer_id": "businesaios-core",
        "issued_at_ms": 1000,
        "expires_at_ms": 2000,
        "policy_id": "policy-1",
        "action": "send_message@v1",
        "payload_hash": payload_hash(decision.payload),
        "snapshot_id": "snapshot-1",
        "state_hash": "state-hash-1",
        "state_schema_version": 1,
        "action_schema_version": 1,
        "kid": "k1",
    }
    assert surface == expected

    secret = b"secret"
    expected_signature = base64.b64encode(
        hmac.new(secret, canonical_json_bytes(expected), hashlib.sha256).digest()
    ).decode("ascii")
    assert sign_decision(decision=decision, secret=secret, kid="k1").signature == expected_signature


def test_v2_signed_surface_binds_decision_contract_hash() -> None:
    contract = _contract()
    decision = _decision(envelope_version=2, contract_v2=contract)
    surface = canonical_signed_payload(
        decision=decision,
        payload_hash_value=payload_hash(decision.payload),
        kid="k1",
    )
    assert surface["envelope_version"] == 2
    assert surface["decision_contract_hash"] == payload_hash(contract)

    keyring = Keyring({"k1": {"secret": b"secret", "revoked": False}}, "k1")
    env = signed_envelope_from_decision(decision=decision, keyring=keyring)
    assert verify_signed_material(
        decision=env.decision,
        payload_hash_value=env.payload_hash,
        signature=env.signature,
        secret=b"secret",
        kid=env.kid,
    )


def test_v2_requires_contract_and_contract_tampering_breaks_signature() -> None:
    with pytest.raises(RuntimeError, match="DECISION_V2_CONTRACT_REQUIRED"):
        sign_decision(
            decision=_decision(envelope_version=2, contract_v2=None),
            secret=b"secret",
            kid="k1",
        )

    contract = _contract()
    decision = _decision(envelope_version=2, contract_v2=contract)
    material = sign_decision(decision=decision, secret=b"secret", kid="k1")
    forged = dict(contract)
    forged["goal_id"] = "goal-forged"
    forged_decision = _decision(envelope_version=2, contract_v2=forged)

    assert not verify_signed_material(
        decision=forged_decision,
        payload_hash_value=material.payload_hash,
        signature=material.signature,
        secret=b"secret",
        kid="k1",
    )



class _EnvelopeState:
    schema_version = 1

    def __init__(self, meta: dict | None = None, product: dict | None = None) -> None:
        self.meta = dict(meta or {})
        self.product = dict(product or {})

    def canonical_bytes(self) -> bytes:
        return b"phase6-decision-v2-state"


def test_v2_builder_uses_real_ranked_alternatives_and_explicit_economics() -> None:
    state = _EnvelopeState(
        meta={"model_profile": "model-profile-1", "do_nothing_baseline": {"profit": 100}},
        product={"business_id": "business-1"},
    )
    out = type(
        "_Out",
        (),
        {
            "action": "send_message@v1",
            "ranking": {
                "_decision_alternatives": [
                    {"option_id": "send_message@v1", "score": 5.0, "reason": "ranked"},
                    {"option_id": "noop@v1", "score": 1.0, "reason": "ranked"},
                ],
                "_decision_selection": {
                    "option_id": "send_message@v1",
                    "score": 5.0,
                    "reason": "ranked",
                },
            },
        },
    )()
    keyring = Keyring({"k1": {"secret": b"secret", "revoked": False}}, "k1")
    built = build_envelope(
        state=state,
        out=out,
        payload={
            "business_id": "business-1",
            "goal_id": "goal-1",
            "expected_value": 25.0,
            "confidence": 0.8,
            "risk": {"level": "low"},
            "meta": {
                "canonical_goal_id": "goal-1",
                "world_model_meta": {
                    "semantic_state_id": "semantic-state-9",
                    "evidence_refs": ["evidence-1"],
                },
            },
        },
        policy_id="policy-1",
        keyring=keyring,
        issuer_id="businesaios-core",
        ttl_ms=1000,
        action_schema_version=1,
        envelope_version=2,
    )
    contract = dict(built.decision.contract_v2 or {})
    assert contract["schema_version"] == 2
    assert contract["business_id"] == "business-1"
    assert contract["goal_id"] == "goal-1"
    assert contract["world_state_version"] == "semantic-state-9"
    assert contract["agent_id"] == "businesaios-core"
    assert contract["model_profile"] == "model-profile-1"
    assert contract["decision_strategy"] == "policy-1"
    assert [item["option_id"] for item in contract["alternatives"]] == [
        "send_message@v1",
        "noop@v1",
    ]
    assert contract["selected_option"]["option_id"] == "send_message@v1"
    assert contract["confidence"] == 0.8
    assert contract["expected_value"] == 25.0
    assert contract["risk"] == {"level": "low"}
    assert contract["do_nothing_baseline"] == {"profit": 100}
    assert contract["rationale"]["evidence"] == ["evidence-1"]
    assert contract["rationale"]["objective_projection"] is None
    assert contract["rationale"]["uncertainties"] == ["objective_vector:UNKNOWN"]


def test_v2_builder_preserves_unknowns_when_no_real_alternatives_or_forecast_exist() -> None:
    state = _EnvelopeState(product={"business_id": "business-2"})
    out = type("_Out", (), {"action": "notify_owner", "ranking": {}})()
    keyring = Keyring({"k1": {"secret": b"secret", "revoked": False}}, "k1")
    built = build_envelope(
        state=state,
        out=out,
        payload={
            "business_id": "business-2",
            "goal_id": "goal-2",
            "meta": {"canonical_goal_id": "goal-2"},
        },
        policy_id="policy-2",
        keyring=keyring,
        issuer_id="businesaios-core",
        ttl_ms=1000,
        action_schema_version=1,
        envelope_version=2,
    )
    contract = dict(built.decision.contract_v2 or {})
    assert contract["alternatives"] is None
    assert contract["world_state_version"] == "UNKNOWN"
    assert contract["model_profile"] == "UNKNOWN"
    assert contract["confidence"] is None
    assert contract["expected_value"] is None
    assert contract["risk"] is None
    assert contract["do_nothing_baseline"] is None
    assert set(contract["rationale"]["uncertainties"]) == {
        "alternatives:UNKNOWN",
        "confidence:UNKNOWN",
        "expected_value:UNKNOWN",
        "objective_vector:UNKNOWN",
        "risk:UNKNOWN",
        "do_nothing_baseline:UNKNOWN",
    }
    assert contract["rationale"]["objective_projection"] is None


def test_v1_builder_does_not_materialize_v2_contract() -> None:
    state = _EnvelopeState(product={"business_id": "business-legacy"})
    out = type("_Out", (), {"action": "notify_owner", "ranking": {}})()
    keyring = Keyring({"k1": {"secret": b"secret", "revoked": False}}, "k1")
    built = build_envelope(
        state=state,
        out=out,
        payload={"business_id": "business-legacy"},
        policy_id="policy-legacy",
        keyring=keyring,
        issuer_id="businesaios-core",
        ttl_ms=1000,
        action_schema_version=1,
        envelope_version=1,
    )
    assert built.decision.contract_v2 is None



def test_v2_archive_roundtrip_preserves_contract_and_signature(tmp_path) -> None:
    contract = _contract()
    decision = _decision(envelope_version=2, contract_v2=contract)
    keyring = Keyring({"k1": {"secret": b"secret", "revoked": False}}, "k1")
    env = signed_envelope_from_decision(decision=decision, keyring=keyring)

    with SqliteDecisionArchive(str(tmp_path / "decision-v2.sqlite3")) as archive:
        archive.put(env)
        loaded = archive.get(decision.decision_id)

    assert loaded is not None
    assert loaded.decision.contract_v2 == contract
    assert loaded.signature == env.signature
    assert loaded.payload_hash == env.payload_hash
    assert verify_signed_material(
        decision=loaded.decision,
        payload_hash_value=loaded.payload_hash,
        signature=loaded.signature,
        secret=b"secret",
        kid=loaded.kid,
    )



def test_v2_rejects_selected_option_or_identity_drift_before_signing() -> None:
    contract = _contract()
    forged_selection = dict(contract)
    forged_selection["selected_option"] = {"option_id": "noop@v1"}
    with pytest.raises(RuntimeError, match="DECISION_V2_SELECTED_OPTION_MISMATCH"):
        sign_decision(
            decision=_decision(envelope_version=2, contract_v2=forged_selection),
            secret=b"secret",
            kid="k1",
        )

    forged_agent = dict(contract)
    forged_agent["agent_id"] = "other-agent"
    with pytest.raises(RuntimeError, match="DECISION_V2_AGENT_ID_MISMATCH"):
        sign_decision(
            decision=_decision(envelope_version=2, contract_v2=forged_agent),
            secret=b"secret",
            kid="k1",
        )

    forged_goal = dict(contract)
    forged_goal["goal_id"] = "goal-forged"
    decision = _decision(envelope_version=2, contract_v2=forged_goal)
    decision.payload["goal_id"] = "goal-1"
    with pytest.raises(RuntimeError, match="DECISION_V2_GOAL_ID_MISMATCH"):
        sign_decision(decision=decision, secret=b"secret", kid="k1")



def test_decision_core_selects_v2_only_for_formal_canonical_goal_binding() -> None:
    assert _decision_envelope_version(
        type(
            "_State",
            (),
            {
                "meta": {
                    "goal_id": "goal-1",
                    "canonical_goal": {"goal": {"goal_id": "goal-1"}},
                }
            },
        )()
    ) == 2
    assert _decision_envelope_version(
        type(
            "_State",
            (),
            {"meta": {"canonical_goal": {"goal": {"goal_id": "goal-1"}}}},
        )()
    ) == 1
    assert _decision_envelope_version(
        type("_State", (), {"meta": {"goal_id": "goal-1"}})()
    ) == 1



def test_v2_preserves_real_complete_objective_projection_without_surrogates() -> None:
    objective = {
        "business_value": 0.7,
        "revenue": 0.8,
        "margin": 0.6,
        "cash_flow": 0.5,
        "risk": 0.9,
        "customer_impact": 0.4,
        "cost": 0.3,
        "strategic_value": 0.75,
    }
    ranking = {
        **{f"objective:{name}": value for name, value in objective.items()},
        "_decision_alternatives": [
            {"option_id": "send_message@v1", "score": 0.61, "reason": "multi_objective"}
        ],
        "_decision_selection": {
            "option_id": "send_message@v1",
            "score": 0.61,
            "reason": "multi_objective",
        },
    }
    state = _EnvelopeState(
        meta={"model_profile": "model-profile-1"},
        product={"business_id": "business-1"},
    )
    out = type(
        "_Out",
        (),
        {"action": "send_message@v1", "ranking": ranking},
    )()
    keyring = Keyring({"k1": {"secret": b"secret", "revoked": False}}, "k1")
    built = build_envelope(
        state=state,
        out=out,
        payload={
            "business_id": "business-1",
            "goal_id": "goal-1",
            "confidence": 0.8,
            "expected_value": 25.0,
            "risk": {"level": "low"},
            "meta": {"canonical_goal_id": "goal-1"},
        },
        policy_id="policy-1",
        keyring=keyring,
        issuer_id="businesaios-core",
        ttl_ms=1000,
        action_schema_version=1,
        envelope_version=2,
    )

    contract = dict(built.decision.contract_v2 or {})
    assert contract["rationale"]["objective_projection"] == objective
    assert "objective_vector:UNKNOWN" not in contract["rationale"]["uncertainties"]
