from execution.evidence_persistence import EvidencePersistenceService
from execution.evidence_verifier import EvidenceVerifier
from execution.world_state_updater import WorldStateUpdater


def test_evidence_verifier_normalizes_router_status_alias() -> None:
    result = EvidenceVerifier().verify(
        action={"action_type": "telegram.send_message", "action_id": "a1"},
        execution_receipt={"ok": True, "status": "executed"},
        router_evidence={"status": "accepted", "ok": True, "external_refs": ["msg:1"]},
    )
    payload = result.to_dict()
    assert payload["verification"]["status"] == "verified"
    assert payload["verification"]["verified"] is True


def test_world_state_updater_stores_canonical_verification_status() -> None:
    update = WorldStateUpdater().build_update(
        verification_result={
            "verified": True,
            "verification": {"status": "accepted", "external_refs": ["msg:1"], "source_of_truth": "router"},
        },
        action={"action_type": "telegram.send_message", "action_id": "a1"},
    )
    row = update.meta_patch["execution_closed_loop"]["last_verification"]
    assert row["verification_status"] == "verified"
    assert row["verified"] is True


def test_evidence_persistence_compacts_to_canonical_status() -> None:
    artifacts = EvidencePersistenceService().build_feedback_artifacts(
        verification_result={
            "verified": True,
            "verification": {"status": "accepted", "code": "accepted", "external_refs": ["msg:1"]},
            "evidence_bundle": {"action_type": "telegram.send_message", "action_id": "a1", "external_refs": ["msg:1"]},
        }
    )
    assert artifacts["persisted_outcome"]["status"] == "verified"
    assert artifacts["persisted_outcome"]["verified"] is True
