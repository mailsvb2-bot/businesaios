from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from application.headless.models import GoalExecutionRequest
from contracts.task import RetryPolicy, TimeoutPolicy
from execution.goal_plan_memory import FileGoalPlanMemoryStore, GoalPlanMemoryService
from execution.headless_contract import HeadlessExecutionContract
from reliability.distributed_lock import InMemoryDistributedLock
from reliability.execution_checkpoint_store import ExecutionCheckpoint, JsonlExecutionCheckpointStore
from reliability.execution_reconciliation import ReconciliationReport
from reliability.idempotency_store import InMemoryIdempotencyStore
from reliability.outbox_store import InMemoryOutboxStore
from reliability.recovery_orchestrator import RecoveryOrchestrator, RecoveryPlan
from runtime.execution.reliability_runtime import RuntimeReliability
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

    def explain(self, *, state: Any, envelope: Any) -> _Explanation:
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



class _TaskRegistry:
    def __init__(
        self,
        status: str,
        *,
        retry_policy: RetryPolicy | None = None,
        timeout_policy: TimeoutPolicy | None = None,
        conflict_keys: tuple[str, ...] = (),
    ) -> None:
        self.status = status
        self.retry_policy = retry_policy
        self.timeout_policy = timeout_policy
        self.conflict_keys = conflict_keys
        self.calls: list[tuple[str, str, str]] = []

    def get(self, *, tenant_id: str, business_id: str, task_id: str):
        self.calls.append((tenant_id, business_id, task_id))
        status = type("Status", (), {"value": self.status})()
        return type(
            "Task",
            (),
            {
                "status": status,
                "retry_policy": self.retry_policy,
                "timeout_policy": self.timeout_policy,
                "conflict_keys": self.conflict_keys,
            },
        )()


def test_phase9_task_bound_execution_requires_canonical_registry(tmp_path: Path) -> None:
    contract = _build_contract(tmp_path)
    request = GoalExecutionRequest(
        goal="execute durable task",
        business_id="biz-1",
        tenant_id="tenant-1",
        meta={"task_id": "task-1"},
    )
    assert request.task_id == "task-1"
    with pytest.raises(RuntimeError, match="canonical task registry"):
        contract.execute_autopilot(request)


def test_phase9_terminal_task_fails_before_headless_effect(tmp_path: Path) -> None:
    contract = _build_contract(tmp_path)
    registry = _TaskRegistry("succeeded")
    contract._task_registry = registry
    request = GoalExecutionRequest(
        goal="execute durable task",
        business_id="biz-1",
        tenant_id="tenant-1",
        meta={"task_id": "task-1"},
    )
    with pytest.raises(ValueError, match="terminal task"):
        contract.execute_autopilot(request)
    assert registry.calls == [("tenant-1", "biz-1", "task-1")]


def test_phase9_blank_task_binding_is_invalid_without_affecting_legacy_requests() -> None:
    invalid = GoalExecutionRequest(
        goal="x",
        business_id="biz-1",
        meta={"task_id": "   "},
    )
    ok, issues = invalid.validate()
    assert ok is False
    assert "invalid:task_id" in issues

    legacy = GoalExecutionRequest(goal="x", business_id="biz-1")
    legacy_ok, legacy_issues = legacy.validate()
    assert legacy_ok is True
    assert "invalid:task_id" not in legacy_issues



@pytest.mark.parametrize("status", ["created", "waiting", "paused", "blocked", "compensating"])
def test_phase9_non_executable_task_states_fail_before_effect(
    tmp_path: Path,
    status: str,
) -> None:
    contract = _build_contract(tmp_path)
    registry = _TaskRegistry(status)
    contract._task_registry = registry
    request = GoalExecutionRequest(
        goal="execute durable task",
        business_id="biz-1",
        tenant_id="tenant-1",
        meta={"task_id": "task-1"},
    )
    with pytest.raises(ValueError, match="not executable"):
        contract.execute_autopilot(request)
    assert registry.calls == [("tenant-1", "biz-1", "task-1")]



def test_phase9_expired_task_deadline_fails_before_effect(tmp_path: Path) -> None:
    contract = _build_contract(tmp_path)
    registry = _TaskRegistry(
        "ready",
        retry_policy=RetryPolicy(max_attempts=2),
        timeout_policy=TimeoutPolicy(task_deadline_ms=1),
    )
    contract._task_registry = registry
    request = GoalExecutionRequest(
        goal="execute durable task",
        business_id="biz-1",
        tenant_id="tenant-1",
        meta={"task_id": "task-1"},
    )
    with pytest.raises(TimeoutError, match="deadline"):
        contract.execute_autopilot(request)
    assert registry.calls == [("tenant-1", "biz-1", "task-1")]



def test_phase9_expired_attempt_deadline_fails_before_executor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = _build_contract(tmp_path)
    registry = _TaskRegistry(
        "ready",
        retry_policy=RetryPolicy(max_attempts=2),
        timeout_policy=TimeoutPolicy(attempt_timeout_ms=1_000),
    )
    contract._task_registry = registry
    calls: list[str] = []

    class _CountingExecutor(StubExecutor):
        def execute(self, env: Any) -> ExecutionResult:
            calls.append(str(env.decision.decision_id))
            return super().execute(env)

    contract._executor = _CountingExecutor()
    monkeypatch.setattr(
        "application.autonomy.autonomy_loop.time",
        SimpleNamespace(time=lambda: 1_000.0),
    )
    monkeypatch.setattr(
        "application.autonomy.autonomy_execution_step.time",
        SimpleNamespace(time=lambda: 1_002.0),
    )
    with pytest.raises(TimeoutError, match="attempt deadline"):
        contract.execute_autopilot(
            GoalExecutionRequest(
                goal="execute durable task",
                business_id="biz-1",
                tenant_id="tenant-1",
                meta={"task_id": "task-1"},
            )
        )
    assert calls == []


def test_phase9_running_task_requires_recovery_checkpoint_owner(tmp_path: Path) -> None:
    contract = _build_contract(tmp_path)
    contract._task_registry = _TaskRegistry("running")
    request = GoalExecutionRequest(
        goal="resume durable task",
        business_id="biz-1",
        tenant_id="tenant-1",
        meta={"task_id": "task-1"},
    )
    with pytest.raises(RuntimeError, match="recovery checkpoints"):
        contract.execute_autopilot(request)


def test_phase9_running_task_without_checkpoint_history_fails_before_effect(
    tmp_path: Path,
) -> None:
    contract = _build_contract(tmp_path)
    contract._task_registry = _TaskRegistry("running")
    calls: list[str] = []

    class _CountingExecutor(StubExecutor):
        def execute(self, env: Any) -> ExecutionResult:
            calls.append(str(env.decision.decision_id))
            return super().execute(env)

    class _CheckpointStore:
        def list_task_runs(self, **kwargs: Any):
            del kwargs
            return ()

    executor = _CountingExecutor()
    executor._reliability = type(
        "Reliability",
        (),
        {"checkpoint_store": _CheckpointStore()},
    )()
    contract._executor = executor

    with pytest.raises(RuntimeError, match="existing recovery checkpoints"):
        contract.execute_autopilot(
            GoalExecutionRequest(
                goal="resume durable task",
                business_id="biz-1",
                tenant_id="tenant-1",
                meta={"task_id": "task-1"},
            )
        )
    assert calls == []


def test_phase9_incomplete_running_task_fails_before_duplicate_effect(tmp_path: Path) -> None:
    contract = _build_contract(tmp_path)
    contract._task_registry = _TaskRegistry("running")

    class _CheckpointStore:
        def list_task_runs(self, **kwargs: Any):
            del kwargs
            return (type("Run", (), {"terminal_stage": None})(),)

    contract._executor._reliability = type(
        "Reliability",
        (),
        {"checkpoint_store": _CheckpointStore()},
    )()
    request = GoalExecutionRequest(
        goal="resume durable task",
        business_id="biz-1",
        tenant_id="tenant-1",
        meta={"task_id": "task-1"},
    )
    with pytest.raises(RuntimeError, match="incomplete execution run"):
        contract.execute_autopilot(request)



def _restart_reliability_from_persisted_task_checkpoints(
    path: Path,
) -> RuntimeReliability:
    rebuilt = JsonlExecutionCheckpointStore(path)
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutboxStore()
    return RuntimeReliability(
        checkpoint_store=rebuilt,
        idempotency_store=idempotency,
        recovery_orchestrator=RecoveryOrchestrator(
            checkpoint_store=rebuilt,
            idempotency_store=idempotency,
            outbox_store=outbox,
        ),
        distributed_lock=InMemoryDistributedLock(),
        scheduler_leader_election=None,
        recovery_leader_election=None,
    )


def test_phase9_persisted_pre_effect_crash_restarts_through_real_recovery_chain(
    tmp_path: Path,
) -> None:
    checkpoint_path = tmp_path / "task-restart.jsonl"
    before_crash = JsonlExecutionCheckpointStore(checkpoint_path)
    before_crash.append(
        ExecutionCheckpoint(
            tenant_id="tenant-1",
            business_id="biz-1",
            task_id="task-1",
            task_run_id="task-run-crashed",
            step_id="task-run-crashed:0",
            run_id="executor-run-crashed",
            sequence_no=0,
            stage="request",
            checkpoint_id="cp-request",
        )
    )

    contract = _build_contract(
        tmp_path,
        executor_ok=True,
        executor_output={"verified": True, "goal_reached": True},
    )
    contract._task_registry = _TaskRegistry("running")
    calls: list[str] = []

    class _CountingExecutor(StubExecutor):
        def execute(self, env: Any) -> ExecutionResult:
            calls.append(str(env.decision.decision_id))
            return super().execute(env)

    restarted_executor = _CountingExecutor(
        ok=True,
        output={"verified": True, "goal_reached": True},
    )
    restarted_executor._reliability = _restart_reliability_from_persisted_task_checkpoints(
        checkpoint_path
    )
    contract._executor = restarted_executor

    report = contract.execute_autopilot(
        GoalExecutionRequest(
            goal="resume durable task",
            business_id="biz-1",
            tenant_id="tenant-1",
            meta={"task_id": "task-1"},
        )
    )

    assert report.completed is True
    assert calls == ["dec-1"]


def test_phase9_persisted_post_effect_crash_does_not_replay_side_effect(
    tmp_path: Path,
) -> None:
    checkpoint_path = tmp_path / "task-post-effect-crash.jsonl"
    before_crash = JsonlExecutionCheckpointStore(checkpoint_path)
    for sequence_no, stage in enumerate(
        ("request", "world_state", "decision", "executable_action", "execution")
    ):
        before_crash.append(
            ExecutionCheckpoint(
                tenant_id="tenant-1",
                business_id="biz-1",
                task_id="task-1",
                task_run_id="task-run-crashed",
                step_id="task-run-crashed:0",
                run_id="executor-run-crashed",
                sequence_no=sequence_no,
                stage=stage,
                checkpoint_id=f"cp-{stage}",
                outbox_message_id=(
                    "decision-crashed" if stage == "execution" else None
                ),
            )
        )

    contract = _build_contract(tmp_path)
    contract._task_registry = _TaskRegistry("running")
    calls: list[str] = []

    class _CountingExecutor(StubExecutor):
        def execute(self, env: Any) -> ExecutionResult:
            calls.append(str(env.decision.decision_id))
            return super().execute(env)

    restarted_executor = _CountingExecutor()
    restarted_executor._reliability = _restart_reliability_from_persisted_task_checkpoints(
        checkpoint_path
    )
    contract._executor = restarted_executor

    with pytest.raises(RuntimeError, match="recovery action required"):
        contract.execute_autopilot(
            GoalExecutionRequest(
                goal="resume durable task",
                business_id="biz-1",
                tenant_id="tenant-1",
                meta={"task_id": "task-1"},
            )
        )
    assert calls == []


def test_phase9_recovery_approved_early_restart_is_allowed(tmp_path: Path) -> None:
    contract = _build_contract(
        tmp_path,
        executor_ok=True,
        executor_output={"verified": True, "goal_reached": True},
    )
    contract._task_registry = _TaskRegistry("running")

    class _CheckpointStore:
        def list_task_runs(self, **kwargs: Any):
            del kwargs
            return (
                type(
                    "Run",
                    (),
                    {"run_id": "task-run-1", "terminal_stage": None},
                )(),
            )

    class _Reliability:
        checkpoint_store = _CheckpointStore()

        def plan_task_run_recovery(self, **kwargs: Any):
            assert kwargs == {
                "tenant_id": "tenant-1",
                "business_id": "biz-1",
                "task_id": "task-1",
                "task_run_id": "task-run-1",
            }
            return RecoveryPlan(
                run_id="executor-run-1",
                recovery_action="restart",
                reason="restart_from_world_state",
                reconciliation=ReconciliationReport(
                    run_id="executor-run-1",
                    latest_stage="world_state",
                    idempotency_state=None,
                    outbox_state=None,
                    checkpoint_count=2,
                ),
                resume_stage="world_state",
            )

    contract._executor._reliability = _Reliability()
    report = contract.execute_autopilot(
        GoalExecutionRequest(
            goal="resume durable task",
            business_id="biz-1",
            tenant_id="tenant-1",
            meta={"task_id": "task-1"},
        )
    )
    assert report.completed is True


def test_phase9_recovery_does_not_blindly_replay_post_decision_run(tmp_path: Path) -> None:
    contract = _build_contract(tmp_path)
    contract._task_registry = _TaskRegistry("running")

    class _CheckpointStore:
        def list_task_runs(self, **kwargs: Any):
            del kwargs
            return (
                type(
                    "Run",
                    (),
                    {"run_id": "task-run-2", "terminal_stage": None},
                )(),
            )

    class _Reliability:
        checkpoint_store = _CheckpointStore()

        def plan_task_run_recovery(self, **kwargs: Any):
            del kwargs
            return RecoveryPlan(
                run_id="executor-run-2",
                recovery_action="resume_execution",
                reason="resume_from_execution",
                reconciliation=ReconciliationReport(
                    run_id="executor-run-2",
                    latest_stage="execution",
                    idempotency_state=None,
                    outbox_state=None,
                    checkpoint_count=4,
                ),
                resume_stage="execution",
            )

    contract._executor._reliability = _Reliability()
    with pytest.raises(RuntimeError, match="recovery action required: resume_execution"):
        contract.execute_autopilot(
            GoalExecutionRequest(
                goal="resume durable task",
                business_id="biz-1",
                tenant_id="tenant-1",
                meta={"task_id": "task-1"},
            )
        )



def test_phase9_conflicting_task_requires_canonical_distributed_lock(tmp_path: Path) -> None:
    contract = _build_contract(tmp_path)
    contract._task_registry = _TaskRegistry(
        "ready",
        conflict_keys=("ledger",),
    )
    with pytest.raises(RuntimeError, match="canonical distributed lock"):
        contract.execute_autopilot(
            GoalExecutionRequest(
                goal="execute durable task",
                business_id="biz-1",
                tenant_id="tenant-1",
                meta={"task_id": "task-1"},
            )
        )


def test_phase9_conflict_lock_blocks_second_task_before_effect(tmp_path: Path) -> None:
    lock = InMemoryDistributedLock()
    contract = _build_contract(tmp_path)
    contract._task_registry = _TaskRegistry(
        "ready",
        conflict_keys=("ledger",),
    )
    contract._executor._reliability = type(
        "Reliability",
        (),
        {"distributed_lock": lock},
    )()

    existing = lock.acquire(
        tenant_id="tenant-1",
        resource="durable-task-conflict:biz-1:ledger",
        owner_id="durable-task:biz-1:other-task",
        ttl_seconds=3600,
    )
    assert existing is not None
    try:
        with pytest.raises(RuntimeError, match="already locked"):
            contract.execute_autopilot(
                GoalExecutionRequest(
                    goal="execute durable task",
                    business_id="biz-1",
                    tenant_id="tenant-1",
                    meta={"task_id": "task-1"},
                )
            )
    finally:
        lock.release(lease=existing)


def test_phase9_conflict_lock_released_after_execution(tmp_path: Path) -> None:
    lock = InMemoryDistributedLock()
    contract = _build_contract(
        tmp_path,
        executor_ok=True,
        executor_output={"verified": True, "goal_reached": True},
    )
    contract._task_registry = _TaskRegistry(
        "ready",
        conflict_keys=("ledger",),
    )
    contract._executor._reliability = type(
        "Reliability",
        (),
        {"distributed_lock": lock},
    )()
    report = contract.execute_autopilot(
        GoalExecutionRequest(
            goal="execute durable task",
            business_id="biz-1",
            tenant_id="tenant-1",
            meta={"task_id": "task-1"},
        )
    )
    assert report.completed is True
    reacquired = lock.acquire(
        tenant_id="tenant-1",
        resource="durable-task-conflict:biz-1:ledger",
        owner_id="durable-task:biz-1:after",
        ttl_seconds=60,
    )
    assert reacquired is not None
    lock.release(lease=reacquired)
