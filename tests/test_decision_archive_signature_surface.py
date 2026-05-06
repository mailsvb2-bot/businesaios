from __future__ import annotations

from core.ai.decision import Decision
from kernel.decision_crypto import signed_envelope_from_decision
from core.security.keyring import Keyring
from observability.platform.decision_archive.sqlite_decision_archive import SqliteDecisionArchive


def test_sqlite_archive_roundtrip_preserves_payload_hash(tmp_path) -> None:
    keyring = Keyring({"k1": {"secret": b"s1", "revoked": False}}, "k1")
    decision = Decision(
        decision_id="d1",
        issuer_id="businesaios-core",
        issued_at_ms=100,
        expires_at_ms=200,
        policy_id="p1",
        action="send_message@v1",
        payload={"user_id": "u1", "text": "hi"},
        snapshot_id="s1",
        state_hash="h1",
        correlation_id="c1",
        state_schema_version=1,
        action_schema_version=1,
        envelope_version=1,
    )
    env = signed_envelope_from_decision(decision=decision, keyring=keyring)

    with SqliteDecisionArchive(str(tmp_path / "archive.db")) as archive:
        archive.put(env)
        loaded = archive.get("d1")

    assert loaded is not None
    assert loaded.payload_hash == env.payload_hash
    assert loaded.signature == env.signature
    assert loaded.kid == env.kid
