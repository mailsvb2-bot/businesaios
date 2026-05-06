from __future__ import annotations

import pytest

from application.decisioning.decision_command import DecisionCommand, DecisionRouteViolation
from core.security.keyring import Keyring


def _command() -> DecisionCommand:
    return DecisionCommand(
        decision_id="d1",
        correlation_id="c1",
        issuer_id="businesaios-core",
        action="send_message@v1",
        payload={"user_id": "u1", "text": "hi"},
        snapshot_id="s1",
        state_hash="h1",
        policy_id="p1",
        issued_at_ms=100,
        expires_at_ms=200,
        state_schema_version=1,
        action_schema_version=1,
        envelope_version=1,
    )


def test_decision_command_cannot_emit_unsigned_envelope() -> None:
    with pytest.raises(DecisionRouteViolation):
        _command().to_envelope()


def test_decision_command_emits_signed_envelope() -> None:
    keyring = Keyring({"k1": {"secret": b"s1", "revoked": False}}, "k1")
    env = _command().to_signed_envelope(keyring)
    assert env.kid == "k1"
    assert env.signature
    assert env.payload_hash
    env.verify()
