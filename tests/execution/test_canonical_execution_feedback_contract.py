from application.effects.canonical_execution_feedback import (
    canonical_execution_feedback,
    canonical_headless_step_artifact,
    canonical_persisted_outcome,
    canonical_world_state_row,
)
from application.effects.effect_verification_bridge import normalize_feedback_contract


def test_normalized_feedback_exposes_canonical_execution_feedback() -> None:
    normalized = normalize_feedback_contract(
        {
            "attempted": True,
            "executed": True,
            "evidence": {
                "router_result": {
                    "status": "success",
                    "verified": True,
                    "confidence": 0.93,
                    "external_refs": ["proof://1"],
                    "action_type": "telegram.send_message",
                }
            },
        }
    )
    snapshot = normalized["execution_feedback"]
    assert snapshot["verification_status"] == "verified"
    assert snapshot["external_refs"] == ["proof://1"]
    assert snapshot["verified"] is True


def test_canonical_contract_shapes_are_consistent() -> None:
    snapshot = canonical_execution_feedback(
        feedback={
            "attempted": True,
            "executed": True,
            "verified": True,
            "verification_status": "accepted",
            "verification_confidence": 0.8,
            "external_refs": ["ext://a"],
            "action_id": "act-1",
        },
        action={
            "action_type": "crm.write_record",
            "decision_id": "dec-1",
            "correlation_id": "corr-1",
        },
    )
    persisted = canonical_persisted_outcome(snapshot)
    world_row = canonical_world_state_row(snapshot)
    artifact = canonical_headless_step_artifact(feedback={**snapshot}, action={"payload": {"x": 1}})
    assert persisted["status"] == world_row["verification_status"] == "verified"
    assert persisted["action_type"] == world_row["action_type"] == "crm.write_record"
    assert artifact["execution_feedback"]["decision_id"] == "dec-1"
    assert artifact["payload"] == {"x": 1}
