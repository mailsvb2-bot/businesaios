from execution.business_memory_policy import BusinessMemoryPolicy
from execution.business_memory_store_support import migrate_business_memory_payload
from execution.closed_loop_economic_state import apply_economic_history_to_state, stable_reliability_trace


def test_closed_loop_economic_state_applies_history_without_drift() -> None:
    state = {"meta": {"economic_feedback_history": [{"event_id": "old"}]}}
    updated = apply_economic_history_to_state(
        world_state=state,
        economic_feedback={"event_id": "new", "status": "ok"},
        roi_history={"event_id": "new", "roi": 1.2},
        policy_snapshot={"snapshot_id": "snap-1", "budget": 10},
    )
    assert updated["meta"]["last_economic_feedback"]["event_id"] == "new"
    assert updated["meta"]["economic_feedback_history"][-1]["event_id"] == "new"


def test_business_memory_store_support_migrates_legacy_payloads() -> None:
    migrated = migrate_business_memory_payload(
        {
            "profile": {"segment": "services"},
            "key_signals": ["signal|weekly|42"],
            "recurring_failures": ["timeout"],
            "last_feedback": {"decision_hint": {"ignored": True}},
        },
        policy=BusinessMemoryPolicy(),
    )
    assert migrated["business_profile"] == {"segment": "services"}
    assert migrated["signal_memory"][0]["name"] == "weekly"
    assert migrated["recurring_failures"][0]["key"] == "timeout"


def test_stable_reliability_trace_is_deterministic() -> None:
    a = stable_reliability_trace(action={"action_type": "send", "action_id": "a1"}, verification={}, execution_receipt={})
    b = stable_reliability_trace(action={"action_type": "send", "action_id": "a1"}, verification={}, execution_receipt={})
    assert a["trace_key"] == b["trace_key"]
