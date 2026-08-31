from application.effects.canonical_execution_feedback import (
    canonical_execution_feedback,
    canonical_headless_step_artifact,
    canonical_persisted_outcome,
    canonical_world_state_row,
)
from application.effects.effect_verification_bridge import normalize_feedback_contract
from execution.world_state_updater import WorldStateUpdater


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
            "intent_id": "intent:dec-1",
            "decision_id": "dec-1",
            "tenant_id": "tenant-1",
            "business_id": "business-1",
            "correlation_id": "corr-1",
        },
    )
    persisted = canonical_persisted_outcome(snapshot)
    world_row = canonical_world_state_row(snapshot)
    artifact = canonical_headless_step_artifact(feedback={**snapshot}, action={"payload": {"x": 1}})
    assert persisted["status"] == world_row["verification_status"] == "verified"
    assert persisted["action_type"] == world_row["action_type"] == "crm.write_record"
    assert persisted["intent_id"] == world_row["intent_id"] == "intent:dec-1"
    assert persisted["business_id"] == world_row["business_id"] == "business-1"
    assert artifact["execution_feedback"]["decision_id"] == "dec-1"
    assert artifact["payload"] == {"x": 1}


def test_feedback_rebuild_preserves_existing_tenant_business_scope() -> None:
    rebuilt = canonical_execution_feedback(
        feedback={
            "attempted": True,
            "executed": True,
            "execution_feedback": {
                "tenant_id": "tenant-1",
                "business_id": "business-1",
            },
        },
        action={
            "action_type": "crm.write_record",
            "action_id": "act-1",
            "decision_id": "dec-1",
            "correlation_id": "corr-1",
        },
    )
    assert rebuilt["tenant_id"] == "tenant-1"
    assert rebuilt["business_id"] == "business-1"


def test_world_state_history_preserves_scoped_execution_identity() -> None:
    action = {
        "action_type": "crm.write_record",
        "action_id": "act-1",
        "intent_id": "intent:dec-1",
        "decision_id": "dec-1",
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "correlation_id": "corr-1",
    }
    verification = {
        "verified": True,
        "verification": {
            "status": "verified",
            "external_refs": ["proof://1"],
            "source_of_truth": "provider_receipt",
        },
    }
    updater = WorldStateUpdater()
    state = updater.apply(world_state={"meta": {}}, update=updater.build_update(verification_result=verification, action=action))
    row = state["meta"]["execution_closed_loop"]["last_verification"]
    assert row["intent_id"] == "intent:dec-1"
    assert row["tenant_id"] == "tenant-1"
    assert row["business_id"] == "business-1"
    assert state["meta"]["execution_closed_loop"]["execution_history"][0]["intent_id"] == "intent:dec-1"
