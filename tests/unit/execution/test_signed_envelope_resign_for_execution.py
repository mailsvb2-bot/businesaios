from __future__ import annotations

from core.ai.decision import Decision
from core.security.keyring import Keyring
from kernel.decision_crypto import signed_envelope_from_decision


def test_resigned_envelope_changes_signature_after_payload_enrich() -> None:
    keyring = Keyring({"k1": {"secret": b"s1", "revoked": False}}, "k1")
    base_decision = Decision(
        decision_id="d1",
        issuer_id="businesaios-core",
        issued_at_ms=100,
        expires_at_ms=200,
        policy_id="p1",
        action="draft_action",
        payload={"tenant_id": "t1"},
        snapshot_id="s1",
        state_hash="h1",
        correlation_id="c1",
        state_schema_version=1,
        action_schema_version=1,
        envelope_version=1,
    )
    env1 = signed_envelope_from_decision(decision=base_decision, keyring=keyring)
    final_decision = Decision(
        decision_id=base_decision.decision_id,
        issuer_id=base_decision.issuer_id,
        issued_at_ms=base_decision.issued_at_ms,
        expires_at_ms=base_decision.expires_at_ms,
        policy_id=base_decision.policy_id,
        action="send_message",
        payload={"tenant_id": "t1", "text": "hi", "autonomy_tier": "bounded_autonomy"},
        snapshot_id=base_decision.snapshot_id,
        state_hash=base_decision.state_hash,
        correlation_id=base_decision.correlation_id,
        state_schema_version=base_decision.state_schema_version,
        action_schema_version=base_decision.action_schema_version,
        envelope_version=base_decision.envelope_version,
    )
    env2 = signed_envelope_from_decision(decision=final_decision, keyring=keyring)
    assert env2.signature != env1.signature
    assert env2.payload_hash != env1.payload_hash
    env2.verify()
