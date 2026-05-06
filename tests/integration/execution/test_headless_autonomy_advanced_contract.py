from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from execution.headless_contract import HeadlessExecutionContract
from application.headless.models import GoalExecutionRequest
from execution.goal_plan_memory import FileGoalPlanMemoryStore, GoalPlanMemoryService
from runtime.execution.executor_result import ExecutionResult


@dataclass(frozen=True)
class _Decision:
    decision_id: str = "dec-1"
    action: str = "notify_owner"
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = "corr-1"


@dataclass(frozen=True)
class _Envelope:
    decision: _Decision


@dataclass(frozen=True)
class _WorldState:
    meta: dict[str, Any] = field(default_factory=dict)


class StubDecisionCore:
    def __init__(self, *, action: str = "notify_owner", payload: dict[str, Any] | None = None) -> None:
        self._action = action
        self._payload = dict(payload or {})

    def optimize(self, state: Any) -> _Envelope:
        return _Envelope(decision=_Decision(action=self._action, payload=dict(self._payload)))


class StubPolicyExplainer:
    @dataclass(frozen=True)
    class _Explanation:
        policy_id: str = "policy-1"
        summary: str = "ok"
        factors: tuple[str, ...] = ()

    def explain(self, *, state: Any, envelope: Any) -> "_Explanation":
        return self._Explanation()


class StubStateMapper:
    def to_world_state(self, *, request: Any, step_index: int, previous_feedback: dict[str, Any]) -> _WorldState:
        return _WorldState(meta={"runtime_capabilities": dict(request.meta.get("runtime_capabilities") or {})})


class StubExecutor:
    def __init__(self, *, ok: bool = True, output: dict[str, Any] | None = None, error: str | None = None) -> None:
        self.ok = ok
        self.output = dict(output or {})
        self.error = error

    def execute(self, env: Any) -> ExecutionResult:
        return ExecutionResult(ok=self.ok, output=dict(self.output), error=self.error, decision_id=str(env.decision.decision_id), correlation_id=str(env.decision.correlation_id))


class StubFeedbackReader:
    def read(self, **kwargs: Any) -> dict[str, Any]:
        result = kwargs.get("result")
        output = dict(getattr(result, "output", {}) or {})
        return {
            "executed": bool(getattr(result, "ok", False)),
            "verified": bool(output.get("verified", getattr(result, "ok", False))),
            "goal_reached": bool(output.get("goal_reached", False)),
            "verification_status": str(output.get("verification_status", "verified" if getattr(result, "ok", False) else "failed")),
            "verification_confidence": float(output.get("verification_confidence", 1.0 if getattr(result, "ok", False) else 0.0)),
            "external_refs": list(output.get("external_refs") or []),
        }


def _build_contract(tmp_path: Path, *, action: str = "notify_owner", payload: dict[str, Any] | None = None, executor_ok: bool = True, executor_output: dict[str, Any] | None = None, executor_error: str | None = None) -> HeadlessExecutionContract:
    goal_plan_service = GoalPlanMemoryService(store=FileGoalPlanMemoryStore(root_dir=tmp_path / "goal_plans"))
    contract = HeadlessExecutionContract(decision_core=StubDecisionCore(action=action, payload=payload), executor=StubExecutor(ok=executor_ok, output=executor_output, error=executor_error), state_mapper=StubStateMapper(), feedback_reader=StubFeedbackReader(), business_memory=None, business_memory_service=None, goal_plan_memory_service=goal_plan_service)
    contract._policy_explainer = StubPolicyExplainer()
    return contract


def test_closed_loop_goal_evaluator_marks_completed_goal(tmp_path: Path) -> None:
    contract = _build_contract(tmp_path, action="notify_owner", payload={"recipient_count": 1}, executor_ok=True, executor_output={"verified": True, "goal_reached": True, "verification_status": "verified", "verification_confidence": 0.95, "external_refs": ["proof://1"]})
    request = GoalExecutionRequest(goal="increase revenue", business_id="biz-1", tenant_id="tenant-1", max_steps=3, autonomy_tier="bounded_autonomy")
    report = contract.execute_autopilot(request)
    assert report.completed is True
    assert report.stop_reason == "goal_achieved"
    assert report.final_feedback["goal_evaluation"]["achieved"] is True
