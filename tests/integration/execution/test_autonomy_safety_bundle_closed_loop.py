from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from execution.autonomy_kill_switch import KillSwitchRule
from execution.headless_contract import HeadlessExecutionContract
from application.headless.models import GoalExecutionRequest
from runtime.execution.executor_result import ExecutionResult
from execution.autonomy_counters import FileAutonomyCounterStore
from execution.autonomy_kill_switch import FileAutonomyKillSwitchRegistry


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
    def optimize(self, state: Any) -> _Envelope:
        return _Envelope(decision=_Decision())


class StubStateMapper:
    def to_world_state(self, *, request: Any, step_index: int, previous_feedback: dict[str, Any]) -> _WorldState:
        return _WorldState(meta={})


class StubExecutor:
    def execute(self, env: Any) -> ExecutionResult:
        return ExecutionResult(ok=True, output={"verified": True, "verification_status": "verified"}, error=None, decision_id=str(env.decision.decision_id), correlation_id=str(env.decision.correlation_id))


def test_kill_switch_denies_before_execution(tmp_path: Path) -> None:
    counter_store = FileAutonomyCounterStore(root_dir=tmp_path / "counters")
    kill_registry = FileAutonomyKillSwitchRegistry(root_dir=tmp_path / "kills")
    kill_registry.replace_rules([KillSwitchRule(tenant_id="tenant-1", business_id="biz-1", integration_domain="internal_execution", action_type="notify_owner", reason="emergency")])
    contract = HeadlessExecutionContract(decision_core=StubDecisionCore(), executor=StubExecutor(), state_mapper=StubStateMapper(), autonomy_counter_store=counter_store, kill_switch_registry=kill_registry)
    request = GoalExecutionRequest(goal="grow", business_id="biz-1", tenant_id="tenant-1", max_steps=1, autonomy_tier="full_autonomy")
    report = contract.execute_autopilot(request)
    assert report.executed is False
    assert report.operator_required is True
    assert report.final_feedback["autonomy_safety"]["reason"] == "kill_switch_active"
