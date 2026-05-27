from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from application.headless.models import GoalExecutionRequest
from execution.headless_contract import HeadlessExecutionContract
from runtime.execution.executor_result import ExecutionResult

pf_mod = pytest.importorskip("execution.performance_feedback_learning")
ch_mod = pytest.importorskip("execution.capability_health_scoring")
mg_mod = pytest.importorskip("execution.multi_goal_planner")

PerformanceFeedbackLearningService = pf_mod.PerformanceFeedbackLearningService
FilePerformanceFeedbackStore = pf_mod.FilePerformanceFeedbackStore
CapabilityHealthScoringService = ch_mod.CapabilityHealthScoringService
FileCapabilityHealthStore = ch_mod.FileCapabilityHealthStore
MultiGoalPlannerService = mg_mod.MultiGoalPlannerService
FileMultiGoalPlannerStore = mg_mod.FileMultiGoalPlannerStore


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
        return _Envelope(
            decision=_Decision(
                action=self._action,
                payload=dict(self._payload),
            )
        )


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
        meta = {
            "runtime_capabilities": dict((request.meta or {}).get("runtime_capabilities") or {}),
            "goal_id": str((request.meta or {}).get("goal_id") or ""),
        }
        return _WorldState(meta=meta)


class StubExecutor:
    def __init__(self, *, ok: bool = True, output: dict[str, Any] | None = None, error: str | None = None) -> None:
        self.ok = ok
        self.output = dict(output or {})
        self.error = error

    def execute(self, env: Any) -> ExecutionResult:
        return ExecutionResult(
            ok=self.ok,
            output=dict(self.output),
            error=self.error,
            decision_id=str(env.decision.decision_id),
            correlation_id=str(env.decision.correlation_id),
        )


class StubFeedbackReader:
    def read(self, **kwargs: Any) -> dict[str, Any]:
        result = kwargs.get("result")
        output = dict(getattr(result, "output", {}) or {})
        executed = bool(getattr(result, "ok", False))
        verified = bool(output.get("verified", executed))
        goal_reached = bool(output.get("goal_reached", False))
        verification_confidence = float(output.get("verification_confidence", 1.0 if verified else 0.0))
        verification_status = str(output.get("verification_status", "verified" if verified else "failed"))
        external_refs = list(output.get("external_refs") or [])
        blocked = bool(output.get("blocked_by_policy", False))
        approval_required = bool(output.get("approval_required", False))
        return {
            "executed": executed,
            "verified": verified,
            "goal_reached": goal_reached,
            "verification_confidence": verification_confidence,
            "verification_status": verification_status,
            "external_refs": external_refs,
            "blocked_by_policy": blocked,
            "approval_required": approval_required,
        }


def _supported_contract_kwargs() -> set[str]:
    return set(inspect.signature(HeadlessExecutionContract.__init__).parameters)


def _require_contract_extensions(*extension_kwargs: str) -> None:
    supported = _supported_contract_kwargs()
    missing = [name for name in extension_kwargs if name not in supported]
    if missing:
        pytest.skip(f"HeadlessExecutionContract does not support extensions: {', '.join(missing)}")


def _build_contract(
    tmp_path: Path,
    *,
    action: str = "notify_owner",
    payload: dict[str, Any] | None = None,
    executor_ok: bool = True,
    executor_output: dict[str, Any] | None = None,
    executor_error: str | None = None,
) -> tuple[Any, Any, Any, Any]:
    performance_service = PerformanceFeedbackLearningService(
        store=FilePerformanceFeedbackStore(root_dir=tmp_path / "performance")
    )
    capability_health_service = CapabilityHealthScoringService(
        store=FileCapabilityHealthStore(root_dir=tmp_path / "cap_health")
    )
    multi_goal_service = MultiGoalPlannerService(
        store=FileMultiGoalPlannerStore(root_dir=tmp_path / "multi_goal")
    )

    optional_kwargs: dict[str, Any] = {}
    supported = _supported_contract_kwargs()
    if "performance_feedback_learning_service" in supported:
        optional_kwargs["performance_feedback_learning_service"] = performance_service
    if "capability_health_scoring_service" in supported:
        optional_kwargs["capability_health_scoring_service"] = capability_health_service
    if "multi_goal_planner_service" in supported:
        optional_kwargs["multi_goal_planner_service"] = multi_goal_service

    contract = HeadlessExecutionContract(
        decision_core=StubDecisionCore(action=action, payload=payload),
        executor=StubExecutor(ok=executor_ok, output=executor_output, error=executor_error),
        state_mapper=StubStateMapper(),
        feedback_reader=StubFeedbackReader(),
        business_memory=None,
        business_memory_service=None,
        **optional_kwargs,
    )
    contract._policy_explainer = StubPolicyExplainer()
    return contract, performance_service, capability_health_service, multi_goal_service


def test_closed_loop_performance_feedback_learning_is_persisted_and_returned(tmp_path: Path) -> None:
    _require_contract_extensions("performance_feedback_learning_service")
    contract, performance_service, _, _ = _build_contract(
        tmp_path,
        action="notify_owner",
        payload={"recipient_count": 1},
        executor_ok=True,
        executor_output={
            "verified": True,
            "goal_reached": False,
            "verification_status": "verified",
            "verification_confidence": 0.9,
            "external_refs": ["proof://perf-1"],
        },
    )
    request = GoalExecutionRequest(
        goal="increase revenue",
        business_id="biz-1",
        tenant_id="tenant-1",
        max_steps=1,
        autonomy_tier="bounded_autonomy",
    )

    report = contract.execute_autopilot(request)
    learned = performance_service.load_context(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal="increase revenue",
    )

    assert "performance_learning" in report.final_feedback
    assert learned["execution_success_rate"] == 1.0
    assert learned["verification_rate"] == 1.0
    assert learned["recommended_budget_posture"] in {"neutral", "expand_carefully"}


def test_closed_loop_performance_posture_tightens_after_bad_history(tmp_path: Path) -> None:
    _require_contract_extensions("performance_feedback_learning_service")
    contract, performance_service, _, _ = _build_contract(
        tmp_path,
        action="launch_campaign",
        payload={"estimated_cost": 2.0},
        executor_ok=False,
        executor_output={"verified": False},
        executor_error="network timeout",
    )

    for _ in range(3):
        request = GoalExecutionRequest(
            goal="increase revenue",
            business_id="biz-1",
            tenant_id="tenant-1",
            max_steps=1,
            autonomy_tier="bounded_autonomy",
        )
        contract.execute_autopilot(request)

    learned = performance_service.load_context(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal="increase revenue",
    )

    assert learned["execution_success_rate"] < 1.0
    assert learned["recommended_budget_posture"] in {"neutral", "tighten"}


def test_closed_loop_capability_health_snapshot_is_updated_after_failure(tmp_path: Path) -> None:
    _require_contract_extensions("capability_health_scoring_service")
    contract, _, capability_service, _ = _build_contract(
        tmp_path,
        action="launch_campaign",
        payload={"estimated_cost": 1.0},
        executor_ok=False,
        executor_output={"verified": False},
        executor_error="network timeout",
    )
    request = GoalExecutionRequest(
        goal="increase revenue",
        business_id="biz-1",
        tenant_id="tenant-1",
        max_steps=1,
        autonomy_tier="bounded_autonomy",
    )

    report = contract.execute_autopilot(request)
    runtime_snapshot = capability_service.load_runtime_snapshot(
        tenant_id="tenant-1",
        capability_keys=["launch_campaign"],
    )

    assert "self_healing_retry" in report.final_feedback
    assert "launch_campaign" in runtime_snapshot
    assert runtime_snapshot["launch_campaign"]["health_tier"] in {
        "healthy",
        "degraded",
        "unhealthy",
        "unknown",
    }


def test_closed_loop_low_health_capability_can_force_notify_owner_fallback(tmp_path: Path) -> None:
    _require_contract_extensions("capability_health_scoring_service")
    contract, _, capability_service, _ = _build_contract(
        tmp_path,
        action="launch_campaign",
        payload={"estimated_cost": 1.0},
        executor_ok=False,
        executor_output={"verified": False},
        executor_error="network timeout",
    )

    for _ in range(6):
        request = GoalExecutionRequest(
            goal="increase revenue",
            business_id="biz-1",
            tenant_id="tenant-1",
            max_steps=1,
            autonomy_tier="bounded_autonomy",
        )
        contract.execute_autopilot(request)

    runtime_capabilities = capability_service.load_runtime_snapshot(
        tenant_id="tenant-1",
        capability_keys=["launch_campaign"],
    )

    contract2, _, _, _ = _build_contract(
        tmp_path,
        action="launch_campaign",
        payload={"estimated_cost": 1.0},
        executor_ok=True,
        executor_output={"verified": True},
    )
    request2 = GoalExecutionRequest(
        goal="increase revenue",
        business_id="biz-1",
        tenant_id="tenant-1",
        max_steps=1,
        autonomy_tier="bounded_autonomy",
        meta={"runtime_capabilities": runtime_capabilities},
    )

    report2 = contract2.execute_autopilot(request2)

    assert "capability_planning" in report2.final_feedback
    assert report2.final_feedback["capability_planning"]["reason"] in {
        "capability_ok",
        "degraded_mode_notify_owner",
        "low_health_score_notify_owner",
    }


def test_closed_loop_multi_goal_queue_is_updated_after_completed_goal(tmp_path: Path) -> None:
    _require_contract_extensions("multi_goal_planner_service")
    contract, _, _, multi_goal_service = _build_contract(
        tmp_path,
        action="notify_owner",
        payload={"recipient_count": 1},
        executor_ok=True,
        executor_output={
            "verified": True,
            "goal_reached": True,
            "verification_status": "verified",
            "verification_confidence": 1.0,
        },
    )

    multi_goal_service.add_goal(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal_id="g1",
        goal="increase revenue",
        priority=90,
        urgency=80,
    )
    multi_goal_service.add_goal(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal_id="g2",
        goal="improve retention",
        priority=70,
        urgency=60,
    )

    request = GoalExecutionRequest(
        goal="increase revenue",
        business_id="biz-1",
        tenant_id="tenant-1",
        max_steps=1,
        autonomy_tier="bounded_autonomy",
        meta={"goal_id": "g1"},
    )

    report = contract.execute_autopilot(request)
    context = multi_goal_service.load_context(tenant_id="tenant-1", business_id="biz-1")
    selection = multi_goal_service.select_next_goal(tenant_id="tenant-1", business_id="biz-1")

    assert report.completed is True
    assert "multi_goal" in report.final_feedback
    queue_by_id = {item["goal_id"]: item for item in context["queue"]}
    assert queue_by_id["g1"]["status"] == "completed"
    assert selection.selected_goal_id in {"g2", None}


def test_closed_loop_multi_goal_blocked_goal_is_not_selected_next(tmp_path: Path) -> None:
    _require_contract_extensions("multi_goal_planner_service")
    contract, _, _, multi_goal_service = _build_contract(
        tmp_path,
        action="launch_campaign",
        payload={"estimated_cost": 50.0},
        executor_ok=True,
    )
    multi_goal_service.add_goal(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal_id="g1",
        goal="increase revenue",
        priority=95,
        urgency=95,
    )
    multi_goal_service.add_goal(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal_id="g2",
        goal="improve retention",
        priority=60,
        urgency=60,
    )

    request = GoalExecutionRequest(
        goal="increase revenue",
        business_id="biz-1",
        tenant_id="tenant-1",
        max_steps=1,
        autonomy_tier="bounded_autonomy",
        economy={"max_run_cost": 1.0},
        meta={"goal_id": "g1"},
    )

    report = contract.execute_autopilot(request)
    selection = multi_goal_service.select_next_goal(tenant_id="tenant-1", business_id="biz-1")

    assert report.operator_required is True
    assert report.final_feedback["goal_evaluation"]["reason"] in {
        "operator_required",
        "policy_blocked",
        "max_steps_reached",
        "continue",
    }
    assert selection.selected_goal_id in {"g2", "g1", None}
