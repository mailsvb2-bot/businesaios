from __future__ import annotations

from application.decision_policy.safety import gate_decision_action
from core.safety.controls.kill_switch.models import KillSwitchSnapshot
from core.safety.controls.multi_step_approval.models import ApprovalTicket
from runtime.boot.safety_control_boot import build_safety_control_runtime


class DummyEventLog:
    def query_recent(self, event_type: str, since_ms: int, filters: dict):
        return []


def test_kill_switch_blocks_matching_action() -> None:
    runtime = build_safety_control_runtime()
    runtime.profile.kill_switch_registry.upsert(KillSwitchSnapshot(action_prefix="capture_payment", active=True, reason="manual_stop"))
    ok, reason, debug = gate_decision_action(
        action="capture_payment@v1",
        payload={"amount": 10},
        tenant_id="t1",
        user_id="u1",
        event_log=DummyEventLog(),
    )
    assert not ok
    assert reason == "kill_switch_active"
    assert debug["control"] == "kill_switch"
    runtime.profile.kill_switch_registry.switches.clear()


def test_multi_step_approval_blocks_when_required_but_missing() -> None:
    ok, reason, debug = gate_decision_action(
        action="deploy_policy@v1",
        payload={"requires_multi_step_approval": True, "approval_id": "ap-1"},
        tenant_id="t1",
        user_id="u1",
        event_log=DummyEventLog(),
    )
    assert not ok
    assert reason == "insufficient_approvals"
    assert debug["control"] == "multi_step_approval"


def test_multi_step_approval_allows_after_ticket_is_seeded() -> None:
    runtime = build_safety_control_runtime()
    runtime.profile.approval_repository.tickets["ap-2"] = ApprovalTicket(action_id="ap-2", approvals=("a", "b"))
    ok, reason, _debug = gate_decision_action(
        action="deploy_policy@v1",
        payload={"requires_multi_step_approval": True, "approval_id": "ap-2", "simulation_required": True, "simulation_score": 0.9},
        tenant_id="t1",
        user_id="u1",
        event_log=DummyEventLog(),
    )
    assert ok
    assert reason == "ok"


def test_simulation_gate_blocks_low_score_when_required() -> None:
    ok, reason, debug = gate_decision_action(
        action="apply_pricing_change@v1",
        payload={"simulation_required": True, "simulation_score": 0.5},
        tenant_id="t1",
        user_id="u1",
        event_log=DummyEventLog(),
    )
    assert not ok
    assert reason == "simulation_gate_blocked"
    assert debug["control"] == "simulation_gate"
