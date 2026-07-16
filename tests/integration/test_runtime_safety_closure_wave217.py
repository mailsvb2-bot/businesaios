from __future__ import annotations

from application.decision_policy.safety import gate_decision_action
from core.safety.controls.action_context import SafetyActionContext
from core.safety.controls.action_identity import canonical_action_id
from core.safety.controls.control_result import ControlStatus
from core.safety.controls.multi_step_approval.models import ApprovalTicket
from runtime.boot.safety_control_boot import build_safety_control_runtime
from runtime.safety_controls import evaluate_runtime_action_controls, record_action_failure, record_execution_outcome


class DummyEventLog:
    def query_recent(self, event_type: str, since_ms: int, filters: dict):
        return []


def test_review_is_fail_closed_in_service_enforce() -> None:
    runtime = build_safety_control_runtime()
    ctx = SafetyActionContext(
        action="capture_payment@v1",
        tenant_id="t1",
        user_id="u1",
        payload={
            "tenant_id": "t1",
            "user_id": "u1",
            "amount": 700,
            "requires_human_review": True,
            "expected_reward": 1.0,
            "expected_margin": 0.5,
            "simulation_required": True,
            "simulation_score": 0.95,
            "simulation_provenance": "sim",
            "simulation_verified": True,
            "approval_id": "ap-rvw",
        },
        metadata={},
    )
    runtime.profile.approval_repository.tickets["ap-rvw"] = ApprovalTicket(action_id="ap-rvw", approvals=("a", "b"))
    decisions = runtime.profile.action_controls.evaluate(ctx)
    assert any(item.status == ControlStatus.REVIEW for item in decisions)


def test_multi_step_approval_uses_stable_action_identity() -> None:
    runtime = build_safety_control_runtime()
    payload = {
        "tenant_id": "t1",
        "user_id": "u1",
        "expected_reward": 1.0,
        "expected_margin": 0.5,
        "simulation_required": True,
        "simulation_score": 0.95,
        "simulation_provenance": "sim",
        "simulation_verified": True,
    }
    approval_id = canonical_action_id(action="deploy_policy@v1", tenant_id="t1", payload=payload)
    runtime.profile.approval_repository.tickets[approval_id] = ApprovalTicket(action_id=approval_id, approvals=("a", "b"))
    decisions = evaluate_runtime_action_controls(action="deploy_policy@v1", payload=payload)
    blocked = [item for item in decisions if item.control == "multi_step_approval" and item.status != ControlStatus.ALLOW]
    assert not blocked


def test_simulation_gate_blocks_explicit_unverified_evidence() -> None:
    decisions = evaluate_runtime_action_controls(
        action="send_marketing_offer@v1",
        payload={
            "tenant_id": "t1",
            "user_id": "u1",
            "expected_reward": 1.0,
            "expected_margin": 0.5,
            "simulation_score": 0.95,
            "simulation_verified": False,
            "simulation_provenance": "",
        },
    )
    blocked = [item for item in decisions if item.control == "simulation_gate" and item.status == ControlStatus.BLOCK]
    assert blocked


def test_circuit_breaker_feedback_opens_after_failures() -> None:
    runtime = build_safety_control_runtime()
    runtime.profile.circuit_breaker_store.states.clear()
    payload = {"tenant_id": "t1", "user_id": "u1"}
    record_action_failure(action="deploy_policy@v1", payload=payload)
    record_action_failure(action="deploy_policy@v1", payload=payload)
    record_action_failure(action="deploy_policy@v1", payload=payload)
    decisions = evaluate_runtime_action_controls(
        action="deploy_policy@v1",
        payload={
            **payload,
            "approval_id": "ap-ok",
            "expected_reward": 1.0,
            "expected_margin": 0.5,
            "simulation_required": True,
            "simulation_score": 0.95,
            "simulation_provenance": "sim",
            "simulation_verified": True,
        },
    )
    blocked = [item for item in decisions if item.control == "circuit_breaker" and item.status == ControlStatus.BLOCK]
    assert blocked


def test_record_execution_outcome_resets_breaker_on_success() -> None:
    runtime = build_safety_control_runtime()
    runtime.profile.circuit_breaker_store.states.clear()
    payload = {"tenant_id": "t1", "user_id": "u1"}
    record_action_failure(action="deploy_policy@v1", payload=payload)
    record_execution_outcome(action="deploy_policy@v1", payload=payload, success=True)
    state = runtime.profile.circuit_breaker_store.get("t1:deploy_policy@v1")
    assert state.consecutive_failures == 0
    assert state.opened is False


def test_gate_decision_action_respects_verified_simulation_and_approvals() -> None:
    runtime = build_safety_control_runtime()
    payload = {
        "tenant_id": "t1",
        "actor_id": "u1",
        "user_id": "u1",
        "expected_reward": 1.0,
        "expected_margin": 0.5,
        "simulation_required": True,
        "simulation_score": 0.95,
        "simulation_provenance": "sim",
        "simulation_verified": True,
    }
    approval_id = canonical_action_id(action="deploy_policy@v1", tenant_id="t1", payload=payload)
    runtime.profile.approval_repository.tickets[approval_id] = ApprovalTicket(action_id=approval_id, approvals=("a", "b"))
    ok, reason, _debug = gate_decision_action(
        action="deploy_policy@v1",
        payload=payload,
        tenant_id="t1",
        user_id="u1",
        event_log=DummyEventLog(),
    )
    assert ok is True
    assert reason == "ok"
