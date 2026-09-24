from __future__ import annotations

import base64
import hashlib
import hmac

import pytest

from contracts.decisioning.sovereign_decision_contract import Decision, DecisionContractV2
from core.security.keyring import Keyring
from core.utils.canonical import canonical_json_bytes, payload_hash
from kernel.decision_crypto import (
    canonical_signed_payload,
    sign_decision,
    signed_envelope_from_decision,
    verify_signed_material,
)


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
