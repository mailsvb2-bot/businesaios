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

def test_headless_closed_loop_reads_router_result_from_feedback_contract() -> None:
    service = HeadlessClosedLoopService(orchestrator=ClosedLoopOrchestrator())
    action = ExecutableAction(action_id="act-1", action_type="website.publish_page", channel="website", decision_id="dec-1", correlation_id="corr-1", objective_name="publish", payload={})
    result = service.enrich(
        request=_Request(), state={"meta": {}}, executable_action=action,
        action_result=ActionResult(action_id="act-1", status="executed", message="submitted", payload={"attempted": True, "executed": True, "verified": False, "operator_required": False}),
        execution_result=_ExecutionResult(output={"message": "submitted"}), autonomy_decision=_AutonomyDecision(),
        feedback={"evidence": {"source": "effect_router", "action_type": "website.publish_page", "status": "verified", "summary": "page live", "external_refs": ["page:42"], "confidence": 1.0, "payload": {"status": "success", "ok": True}}},
    )
    assert result.feedback["verified"] is True
    assert result.feedback["verification_status"] == "verified"
    assert result.cycle_result.verification_result["verification"]["source_of_truth"] == "router"
