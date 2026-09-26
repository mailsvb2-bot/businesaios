from __future__ import annotations

import pytest

from contracts.decisioning.sovereign_decision_contract import Decision, DecisionContractV2
from core.security.keyring import Keyring
from kernel.decision_crypto import signed_envelope_from_decision
from runtime.enforcement.signature_gate import verify_signature_and_integrity
from runtime.guard_protocols import SUPPORTED_ENVELOPE_VERSION, SUPPORTED_ENVELOPE_VERSIONS


class _Schemas:
    def validate(self, action, payload, version=None):
        assert action == "send_message@v1"
        assert isinstance(payload, dict)
        assert version == 1
        return 1


def _decision(version: int) -> Decision:
    contract = None
    if version >= 2:
        contract = DecisionContractV2(
            business_id="business-1",
            goal_id="goal-1",
            world_state_version="semantic-state-1",
            agent_id="businesaios-core",
            model_profile="UNKNOWN",
            decision_strategy="policy-1",
            alternatives=None,
            selected_option={"option_id": "send_message@v1"},
            rationale={
                "evidence": [],
                "constraints": None,
                "alternatives": None,
                "selection_reason": "UNKNOWN",
                "uncertainties": ["alternatives:UNKNOWN"],
                "expected_outcome": None,
                "risk": None,
            },
            created_at=1000,
        ).as_dict()
    return Decision(
        decision_id=f"decision-v{version}",
        issuer_id="businesaios-core",
        issued_at_ms=1000,
        expires_at_ms=5000,
        policy_id="policy-1",
        action="send_message@v1",
        payload={"tenant_id": "tenant-1", "text": "hello"},
        snapshot_id=f"snapshot-v{version}",
        state_hash=f"state-v{version}",
        correlation_id=f"correlation-v{version}",
        state_schema_version=1,
        action_schema_version=1,
        envelope_version=version,
        contract_v2=contract,
    )


def _verify(version: int, supported_versions: tuple[int, ...] | None) -> None:
    keyring = Keyring({"k1": {"secret": b"secret", "revoked": False}}, "k1")
    env = signed_envelope_from_decision(decision=_decision(version), keyring=keyring)
    verify_signature_and_integrity(
        env=env,
        keyring=keyring,
        schemas=_Schemas(),
        expected_issuer_id="businesaios-core",
        supported_envelope_version=SUPPORTED_ENVELOPE_VERSION,
        supported_envelope_versions=supported_versions,
        max_replay_ms=10_000,
        ttl_skew_ms=0,
        now_ms=2000,
    )


def test_runtime_guard_explicitly_supports_v1_and_v2() -> None:
    assert SUPPORTED_ENVELOPE_VERSION == 1
    assert SUPPORTED_ENVELOPE_VERSIONS == (1, 2)
    _verify(1, SUPPORTED_ENVELOPE_VERSIONS)
    _verify(2, SUPPORTED_ENVELOPE_VERSIONS)


def test_legacy_single_version_call_still_accepts_only_v1() -> None:
    _verify(1, None)
    with pytest.raises(RuntimeError, match="UNSUPPORTED_ENVELOPE_VERSION"):
        _verify(2, None)


def test_runtime_guard_rejects_unknown_future_envelope_version() -> None:
    keyring = Keyring({"k1": {"secret": b"secret", "revoked": False}}, "k1")
    decision = _decision(2)
    decision = Decision(**{**decision.__dict__, "envelope_version": 3})
    env = signed_envelope_from_decision(decision=decision, keyring=keyring)
    with pytest.raises(RuntimeError, match="UNSUPPORTED_ENVELOPE_VERSION"):
        verify_signature_and_integrity(
            env=env,
            keyring=keyring,
            schemas=_Schemas(),
            expected_issuer_id="businesaios-core",
            supported_envelope_version=SUPPORTED_ENVELOPE_VERSION,
            supported_envelope_versions=SUPPORTED_ENVELOPE_VERSIONS,
            max_replay_ms=10_000,
            ttl_skew_ms=0,
            now_ms=2000,
        )
