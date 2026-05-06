from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from execution.business_operating_memory import (
    BusinessMemoryCompactor,
    BusinessMemoryPolicy,
    FileBusinessOperatingMemoryStore,
)
from execution.capability_health_scoring import (
    CapabilityHealthScoringService,
    FileCapabilityHealthStore,
)
from application.effects.effect_journal import FileEffectJournal
from execution.goal_plan_memory import (
    FileGoalPlanMemoryStore,
    GoalPlanMemoryService,
    GoalPlanSnapshot,
)
from execution.goal_score import GoalScoreEngine
from execution.headless_contract import HeadlessExecutionContract
from application.headless.feedback import SimpleHeadlessFeedbackReader
from execution.headless_ledger import FileHeadlessLedger
from application.headless.models import GoalExecutionReport, GoalExecutionRequest
from execution.headless_replay import HeadlessReplayEngine
from execution.headless_state_store import FileHeadlessStateStore
from execution.idempotency_guard import FileIdempotencyGuard
from execution.multi_goal_planner import (
    FileMultiGoalPlannerStore,
    MultiGoalPlannerService,
)
from execution.operator_handoff import FileOperatorHandoffStore
from execution.outcome_normalizer import OutcomeNormalizer
from execution.owner_path import FileOwnerPathStore, OwnerPathService
from execution.performance_feedback_learning import (
    FilePerformanceFeedbackStore,
    PerformanceFeedbackLearningService,
)
from execution.policy_explainer import PolicyExplainer
from execution.retry_executor_policy import RetryExecutorPolicy
from application.learning.retry_taxonomy import RetryTaxonomy
from execution.scenario_goal_score import ScenarioGoalScoreEngine
from runtime.execution.executor_result import ExecutionResult
from runtime.platform.business_memory.service import BusinessMemoryService
from runtime.platform.business_memory.store import FileBusinessMemoryStore


@dataclass(frozen=True)
class FakeDecision:
    decision_id: str
    correlation_id: str
    action: str
    payload: dict[str, Any]
    policy_id: str = "policy:e2e"


@dataclass(frozen=True)
class FakeEnvelope:
    decision: FakeDecision
    policy: object | None = None


@dataclass(frozen=True)
class FakeWorldState:
    meta: dict[str, Any] = field(default_factory=dict)
    behavior: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScenarioStep:
    action_type: str
    output: dict[str, Any] = field(default_factory=dict)
    ok: bool = True
    error: str | None = None
    decision_id: str | None = None
    correlation_id: str | None = None
    decision_payload: dict[str, Any] = field(default_factory=dict)


class FakeDecisionCore:
    def __init__(self, scenario: list[ScenarioStep]) -> None:
        self._scenario = list(scenario)
        self._index = 0

    def optimize(self, state: Any) -> FakeEnvelope:
        del state
        if not self._scenario:
            raise RuntimeError("empty_scenario")
        idx = min(self._index, len(self._scenario) - 1)
        step = self._scenario[idx]
        self._index += 1
        return FakeEnvelope(
            decision=FakeDecision(
                decision_id=step.decision_id or f"dec-{idx + 1}",
                correlation_id=step.correlation_id or f"corr-{idx + 1}",
                action=step.action_type,
                payload=dict(step.decision_payload),
            )
        )


class FakeExecutor:
    def __init__(self, scenario: list[ScenarioStep]) -> None:
        self._scenario = list(scenario)
        self.calls = 0
        self.seen_actions: list[str] = []

    def execute(self, envelope: Any) -> ExecutionResult:
        idx = min(self.calls, len(self._scenario) - 1)
        step = self._scenario[idx]
        self.calls += 1
        self.seen_actions.append(str(envelope.decision.action))
        return ExecutionResult(
            ok=bool(step.ok),
            output=dict(step.output),
            error=step.error,
            decision_id=str(envelope.decision.decision_id),
            correlation_id=str(envelope.decision.correlation_id),
        )


class FakeStateMapper:
    def __init__(self, runtime_capabilities: dict[str, Any] | None = None) -> None:
        self._runtime_capabilities = dict(runtime_capabilities or {})

    def to_world_state(
        self,
        *,
        request: GoalExecutionRequest,
        step_index: int,
        previous_feedback: dict[str, Any],
    ) -> FakeWorldState:
        runtime_capabilities = dict(self._runtime_capabilities)
        if not runtime_capabilities:
            runtime_capabilities = dict((request.meta or {}).get("runtime_capabilities") or {})
        if not runtime_capabilities:
            runtime_capabilities["create_listing"] = {
                "enabled": True,
                "healthy": True,
                "health_score": 1.0,
            }
        return FakeWorldState(
            meta={
                "goal": request.goal,
                "step_index": int(step_index),
                "constraints": dict(request.constraints),
                "economy": dict(request.economy),
                "autonomy_tier": request.autonomy_tier,
                "approval_policy": dict(request.approval_policy),
                "runtime_capabilities": runtime_capabilities,
                "previous_feedback": dict(previous_feedback),
                "goal_id": str((request.meta or {}).get("goal_id") or ""),
            },
            behavior={"goal": request.goal},
        )


@dataclass
class EnterpriseHarness:
    contract: HeadlessExecutionContract
    ledger: FileHeadlessLedger
    state_store: FileHeadlessStateStore
    effect_journal: FileEffectJournal
    business_memory_store: FileBusinessOperatingMemoryStore
    runtime_business_memory_service: BusinessMemoryService
    goal_plan_store: FileGoalPlanMemoryStore
    goal_plan_service: GoalPlanMemoryService
    performance_service: PerformanceFeedbackLearningService
    capability_health_service: CapabilityHealthScoringService
    multi_goal_service: MultiGoalPlannerService
    executor: FakeExecutor
    replay: HeadlessReplayEngine

    def run(self, request: GoalExecutionRequest) -> GoalExecutionReport:
        return self.contract.execute_autopilot(request)

    def read_ledger_records(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.ledger.root_dir.glob("*.json")):
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        return rows

    def read_single_ledger_record(self) -> dict[str, Any]:
        rows = self.read_ledger_records()
        assert len(rows) == 1, f"expected 1 ledger record, got {len(rows)}"
        return rows[0]

    def read_latest_state_snapshot(self, run_id: str) -> dict[str, Any]:
        return self.state_store.load_latest_snapshot(run_id=run_id)

    def read_effect_rows(self, run_id: str) -> list[dict[str, Any]]:
        return self.effect_journal.read_all(run_id=run_id)


def build_harness(
    tmp_path: Path,
    *,
    scenario: list[ScenarioStep],
    runtime_capabilities: dict[str, Any] | None = None,
    include_idempotency: bool = True,
) -> EnterpriseHarness:
    memory_policy = BusinessMemoryPolicy()
    business_memory_store = FileBusinessOperatingMemoryStore(
        root_dir=tmp_path / "business_memory",
        policy=memory_policy,
        compactor=BusinessMemoryCompactor(policy=memory_policy),
    )
    runtime_business_memory_service = BusinessMemoryService(
        store=FileBusinessMemoryStore(root_dir=tmp_path / "runtime_business_memory")
    )
    ledger = FileHeadlessLedger(root_dir=tmp_path / "ledger")
    state_store = FileHeadlessStateStore(root_dir=tmp_path / "state")
    effect_journal = FileEffectJournal(root_dir=tmp_path / "effects")
    goal_plan_store = FileGoalPlanMemoryStore(root_dir=tmp_path / "goal_plan")
    goal_plan_service = GoalPlanMemoryService(store=goal_plan_store)
    performance_service = PerformanceFeedbackLearningService(
        store=FilePerformanceFeedbackStore(root_dir=tmp_path / "performance")
    )
    capability_health_service = CapabilityHealthScoringService(
        store=FileCapabilityHealthStore(root_dir=tmp_path / "capability_health")
    )
    multi_goal_service = MultiGoalPlannerService(
        store=FileMultiGoalPlannerStore(root_dir=tmp_path / "multi_goal")
    )
    owner_path_service = OwnerPathService(
        store=FileOwnerPathStore(root_dir=tmp_path / "owner_path")
    )
    executor = FakeExecutor(scenario=scenario)

    contract = HeadlessExecutionContract(
        decision_core=FakeDecisionCore(scenario=scenario),
        executor=executor,
        state_mapper=FakeStateMapper(runtime_capabilities=runtime_capabilities),
        feedback_reader=SimpleHeadlessFeedbackReader.default(),
        ledger=ledger,
        business_memory=business_memory_store,
        business_memory_service=runtime_business_memory_service,
        state_store=state_store,
        effect_journal=effect_journal,
        idempotency_guard=FileIdempotencyGuard(root_dir=tmp_path / "idempotency")
        if include_idempotency
        else None,
        goal_score_engine=GoalScoreEngine(),
        retry_taxonomy=RetryTaxonomy(),
        policy_explainer=PolicyExplainer(),
        outcome_normalizer=OutcomeNormalizer(),
        retry_executor_policy=RetryExecutorPolicy(max_attempts=2),
        operator_handoff_store=FileOperatorHandoffStore(root_dir=tmp_path / "handoff"),
        scenario_goal_score_engine=ScenarioGoalScoreEngine(base=GoalScoreEngine()),
        goal_plan_memory_service=goal_plan_service,
        performance_feedback_learning_service=performance_service,
        capability_health_scoring_service=capability_health_service,
        multi_goal_planner_service=multi_goal_service,
        owner_path_service=owner_path_service,
    )

    return EnterpriseHarness(
        contract=contract,
        ledger=ledger,
        state_store=state_store,
        effect_journal=effect_journal,
        business_memory_store=business_memory_store,
        runtime_business_memory_service=runtime_business_memory_service,
        goal_plan_store=goal_plan_store,
        goal_plan_service=goal_plan_service,
        performance_service=performance_service,
        capability_health_service=capability_health_service,
        multi_goal_service=multi_goal_service,
        executor=executor,
        replay=HeadlessReplayEngine(contract=contract),
    )


def make_request(
    *,
    goal: str = "Acquire a verified lead",
    business_id: str = "biz-1",
    tenant_id: str = "tenant-1",
    max_steps: int = 1,
    autonomy_tier: str = "bounded_autonomy",
    constraints: dict[str, Any] | None = None,
    economy: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    approval_policy: dict[str, Any] | None = None,
) -> GoalExecutionRequest:
    return GoalExecutionRequest(
        goal=goal,
        business_id=business_id,
        tenant_id=tenant_id,
        max_steps=max_steps,
        autonomy_tier=autonomy_tier,
        constraints=dict(constraints or {}),
        economy=dict(economy or {}),
        meta=dict(meta or {}),
        approval_policy=dict(approval_policy or {}),
    )


def seed_goal_plan(
    harness: EnterpriseHarness,
    *,
    tenant_id: str,
    business_id: str,
    goal: str,
    plan_id: str,
    next_focus: str | None,
    remaining_action_hints: tuple[str, ...] = (),
    plan_status: str = "open",
) -> None:
    harness.goal_plan_store.save(
        GoalPlanSnapshot(
            tenant_id=tenant_id,
            business_id=business_id,
            goal=goal,
            plan_id=plan_id,
            plan_status=plan_status,
            next_focus=next_focus,
            remaining_action_hints=remaining_action_hints,
        )
    )
