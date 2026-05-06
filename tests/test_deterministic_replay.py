from core.ai.decision_archive import MemoryDecisionArchive
from runtime.replay import ReplayEngine


def test_deterministic_replay():
    archive = MemoryDecisionArchive()
    engine = ReplayEngine(archive)

    # Store a bit-exact envelope and replay it.
    from core.ai.decision import Decision, DecisionEnvelope

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
