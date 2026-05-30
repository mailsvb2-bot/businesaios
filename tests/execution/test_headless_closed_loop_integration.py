from __future__ import annotations

from dataclasses import dataclass

from application.headless.closed_loop import HeadlessClosedLoopService
from contracts.action_result import ActionResult
from contracts.executable_action import ExecutableAction
from execution.closed_loop_orchestrator import ClosedLoopOrchestrator


@dataclass
class _Request:
    tenant_id: str = "tenant-1"
    business_id: str = "biz-1"
    autonomy_tier: str = "supervised"
@dataclass
class _ExecutionResult:
    ok: bool = True
    error: str | None = None
    output: dict | None = None
@dataclass
class _AutonomyDecision:
    action_class: str = "effectful"
    tier: str = "supervised"
    approval_required: bool = False
    blocked_by_policy: bool = False

def _build_service() -> HeadlessClosedLoopService: return HeadlessClosedLoopService(orchestrator=ClosedLoopOrchestrator())

def test_enrich_uses_existing_feedback_and_does_not_reexecute() -> None:
    service = _build_service()
    calls = {"count": 0}
    feedback = {"verified": True, "verification_status": "verified", "verification_confidence": 1.0, "external_refs": ["ext-1"], "evidence": {"router_result": {"verified": True, "status": "verified", "code": "verified", "message": "ok", "confidence": 1.0, "external_refs": ["ext-1"]}}}
    action = ExecutableAction(action_id="act-1", action_type="publish_page", channel="headless", decision_id="dec-1", correlation_id="corr-1", objective_name="publish", payload={})
    execution_result = _ExecutionResult(output={"message": "submitted"})
    def executor_should_not_run(*args, **kwargs):
        calls["count"] += 1
        raise AssertionError("should not re-execute")
    artifacts = service.enrich(request=_Request(), state={"meta": {}}, executable_action=action, action_result=ActionResult(action_id="act-1", status="executed", message="submitted", payload={"attempted": True, "executed": True, "verified": False, "operator_required": False}), execution_result=execution_result, autonomy_decision=_AutonomyDecision(), feedback=feedback)
    assert calls["count"] == 0
    assert artifacts.feedback["verified"] is True
    assert artifacts.feedback["verification_status"] == "verified"
    assert artifacts.feedback["next_tier_context"]["ceiling_tier"] in {"supervised", "bounded_autonomy", "full_autonomy"}
