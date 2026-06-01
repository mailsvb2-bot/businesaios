from __future__ import annotations

from execution.closed_loop_orchestrator import ClosedLoopCycleInput, ClosedLoopOrchestrator


def _cycle(action, **kwargs):
    return ClosedLoopOrchestrator().run_cycle(cycle_input=ClosedLoopCycleInput(action=action, world_state=kwargs.pop("world_state", {"meta": {}}), execution_receipt=kwargs.pop("execution_receipt", {"status": "executed"}), feedback=kwargs.pop("feedback", {}), router_evidence=kwargs.pop("router_evidence", {}), requested_tier=kwargs.pop("requested_tier", "supervised"), current_tier=kwargs.pop("current_tier", "supervised"), **kwargs))

def test_success_with_external_evidence() -> None:
    result = _cycle({"action_type": "publish_page"}, feedback={"evidence": {"router_result": {"verified": True, "status": "verified", "code": "verified", "message": "page is live", "confidence": 1.0, "external_refs": ["page:123"]}}})
    assert result.verification_result["verified"] is True
    assert result.verification_result["verification"]["status"] == "verified"

def test_success_denied_by_missing_external_confirmation() -> None:
    result = _cycle({"action_type": "launch_campaign"})
    assert result.verification_result["verified"] is False
    assert result.verification_result["verification"]["outcome"]["verification_status"] == "missing_external_confirmation"

def test_router_explicit_verdict_override() -> None:
    result = _cycle({"action_type": "send_email"}, router_evidence={"verified": False, "status": "unverified", "code": "router_denied", "message": "router saw conflict", "confidence": 0.9})
    assert result.verification_result["verified"] is False
    assert result.verification_result["verification"]["source_of_truth"] == "router"
    assert result.verification_result["verification"]["code"] == "router_denied"

def test_repeated_update_without_history_duplication() -> None:
    first = _cycle({"action_type": "publish_page", "action_id": "act-1"}, feedback={"evidence": {"router_result": {"verified": True, "status": "verified", "external_refs": ["page:1"]}}})
    second = _cycle({"action_type": "publish_page", "action_id": "act-1"}, world_state=first.world_state, feedback={"evidence": {"router_result": {"verified": True, "status": "verified", "external_refs": ["page:1"]}}})
    history = second.world_state["meta"]["execution_closed_loop"]["execution_history"]
    keys = {(row.get("action_type"), row.get("action_id"), row.get("verification_status")) for row in history}
    assert len(keys) == len(history)

def test_next_tier_context_after_verified_unverified_runs() -> None:
    ok = _cycle({"action_type": "publish_page", "action_id": "ok-1"}, requested_tier="bounded_autonomy", feedback={"evidence": {"router_result": {"verified": True, "status": "verified", "external_refs": ["page:ok"]}}})
    bad = _cycle({"action_type": "launch_campaign", "action_id": "bad-1"}, world_state=ok.world_state, requested_tier="bounded_autonomy", current_tier=ok.next_tier_context["suggested_tier"])
    assert ok.next_tier_context["suggested_tier"] in {"supervised", "bounded_autonomy"}
    assert bad.next_tier_context["suggested_tier"] in {"advisory", "supervised", "bounded_autonomy"}
