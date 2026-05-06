from __future__ import annotations

from typing import Any

from execution.action_budget_engine import ActionBudgetEngine
from execution.autonomy_counters import AutonomyCounterResolver, FileAutonomyCounterStore
from application.autonomy.autonomy_kill_switch import FileAutonomyKillSwitchRegistry
from application.autonomy.autonomy_safety_bundle import AutonomySafetyBundle
from execution.recent_actions import RecentActionsSource
from application.autonomy.autonomy_loop import AutonomyLoop
from application.autonomy.autonomy_policy import AutonomyPolicy
from execution.blast_radius_guard import BlastRadiusGuard
from execution.bounded_autonomy import BoundedAutonomyGuard
from application.memory.business_memory_state_adapter import BusinessMemoryStateAdapter
from application.memory.business_operating_memory import FileBusinessOperatingMemoryStore
from application.capability.capability_aware_planning import CapabilityAwarePlanner
from application.capability.capability_health_registry import CapabilityHealthRegistry
from application.capability.capability_matrix import CapabilityMatrix
from application.capability.capability_router import ExecutionCapabilityRouter
from execution.closed_loop_orchestrator import ClosedLoopOrchestrator
from application.effects.effect_journal import FileEffectJournal
from execution.evidence.router import EvidenceRouter, build_evidence_router
from application.evidence.evidence_persistence import EvidencePersistenceService
from execution.goal_evaluator import GoalEvaluator
from application.planning.goal_plan_memory import GoalPlanMemoryService
from execution.goal_score import GoalScoreEngine
from execution.performance_feedback_learning import PerformanceFeedbackLearningService
from application.capability.capability_health_scoring import CapabilityHealthScoringService
from execution.canonical_run_artifacts import canonical_goal_execution_report
from application.planning.multi_goal_planner import MultiGoalPlannerService
from application.headless.closed_loop import HeadlessClosedLoopService
from application.headless.decision_gateway import validate_headless_decision_core
from application.headless.execution_gateway import validate_headless_executor
from execution.optimization.adaptive_optimization_service import AdaptiveOptimizationService
from execution.headless_ledger import FileHeadlessLedger, LedgerRecord
from application.headless.models import CEOParticipation, GoalExecutionReport, GoalExecutionRequest, GoalExecutionStep
from application.headless.step_builder import HeadlessStepBuilder
from application.headless.stop_policy import HeadlessStopPolicy
from execution.idempotency_guard import FileIdempotencyGuard
from execution.operator_handoff import FileOperatorHandoffStore
from execution.operator_handoff_policy import OperatorHandoffPolicy
from execution.opportunity_detector import OpportunityDetector
from execution.outcome_normalizer import OutcomeNormalizer
from execution.policy_explainer import PolicyExplainer
from execution.retry_executor_policy import RetryExecutorPolicy
from application.learning.retry_taxonomy import RetryTaxonomy
from execution.revenue_outcome import RevenueOutcomeProjector
from execution.scenario_goal_score import ScenarioGoalScoreEngine
from execution.self_healing_retry import SelfHealingRetryEngine
from execution.safe_self_driving import SafeSelfDrivingPolicy
from execution.world_state_updater import WorldStateUpdater
from runtime.platform.business_memory.service import BusinessMemoryService


CANON_HEADLESS_EXECUTION_CONTRACT = True


def _require_method(value: Any, name: str, owner: str) -> None:
    if value is None or not callable(getattr(value, name, None)):
        raise ValueError(f'{owner} must provide callable {name}()')



def _canonical_matrix(*candidates: Any) -> CapabilityMatrix:
    for candidate in candidates:
        if isinstance(candidate, CapabilityMatrix):
            return candidate
    return CapabilityMatrix()


def _router_matrix(router: Any) -> CapabilityMatrix | None:
    value = getattr(router, '_matrix', None)
    return value if isinstance(value, CapabilityMatrix) else None


def _router_registry(router: Any) -> CapabilityHealthRegistry | None:
    value = getattr(router, '_health_registry', None)
    return value if isinstance(value, CapabilityHealthRegistry) else None


def _planner_router(planner: Any) -> ExecutionCapabilityRouter | None:
    value = getattr(planner, '_router', None)
    return value if isinstance(value, ExecutionCapabilityRouter) else None


class HeadlessExecutionContract:
    def __init__(
        self,
        *,
        decision_core: Any,
        executor: Any,
        state_mapper: Any,
        feedback_reader: Any | None = None,
        stop_policy: HeadlessStopPolicy | None = None,
        ledger: FileHeadlessLedger | None = None,
        business_memory: FileBusinessOperatingMemoryStore | None = None,
        state_store: Any | None = None,
        effect_journal: FileEffectJournal | None = None,
        idempotency_guard: FileIdempotencyGuard | None = None,
        goal_score_engine: GoalScoreEngine | None = None,
        retry_taxonomy: RetryTaxonomy | None = None,
        policy_explainer: PolicyExplainer | None = None,
        outcome_normalizer: OutcomeNormalizer | None = None,
        retry_executor_policy: RetryExecutorPolicy | None = None,
        operator_handoff_store: FileOperatorHandoffStore | None = None,
        scenario_goal_score_engine: ScenarioGoalScoreEngine | None = None,
        evidence_router: EvidenceRouter | None = None,
        business_memory_service: BusinessMemoryService | None = None,
        step_builder: HeadlessStepBuilder | None = None,
        operator_handoff_policy: OperatorHandoffPolicy | None = None,
        blast_radius_guard: BlastRadiusGuard | None = None,
        bounded_autonomy_guard: BoundedAutonomyGuard | None = None,
        safe_self_driving_policy: SafeSelfDrivingPolicy | None = None,
        decision_keyring: Any | None = None,
        revenue_outcome_projector: RevenueOutcomeProjector | None = None,
        event_log: Any | None = None,
        action_budget_engine: ActionBudgetEngine | None = None,
        capability_aware_planner: CapabilityAwarePlanner | None = None,
        capability_matrix: CapabilityMatrix | None = None,
        capability_health_registry: CapabilityHealthRegistry | None = None,
        execution_capability_router: ExecutionCapabilityRouter | None = None,
        goal_evaluator: GoalEvaluator | None = None,
        goal_plan_memory_service: GoalPlanMemoryService | None = None,
        self_healing_retry_engine: SelfHealingRetryEngine | None = None,
        evidence_persistence_service: EvidencePersistenceService | None = None,
        performance_feedback_learning_service: PerformanceFeedbackLearningService | None = None,
        capability_health_scoring_service: CapabilityHealthScoringService | None = None,
        adaptive_optimization_service: AdaptiveOptimizationService | None = None,
        multi_goal_planner_service: MultiGoalPlannerService | None = None,
        autonomy_counter_store: FileAutonomyCounterStore | None = None,
        kill_switch_registry: FileAutonomyKillSwitchRegistry | None = None,
        recent_actions_source: RecentActionsSource | None = None,
        autonomy_safety_bundle: AutonomySafetyBundle | None = None,
        owner_path_service: Any | None = None,
    ) -> None:
        try:
            validate_headless_decision_core(decision_core)
        except Exception as exc:
            raise ValueError('decision_core must provide callable issue() or optimize()') from exc
        validate_headless_executor(executor)
        _require_method(state_mapper, 'to_world_state', 'state_mapper')
        self._decision_core = decision_core
        self._executor = executor
        self._state_mapper = state_mapper
        self._feedback_reader = feedback_reader
        self._stop_policy = stop_policy or HeadlessStopPolicy()
        self._ledger = ledger
        self._business_memory = business_memory
        self._state_store = state_store
        self._effect_journal = effect_journal
        self._idempotency_guard = idempotency_guard
        self._goal_score_engine = goal_score_engine or GoalScoreEngine()
        self._retry_taxonomy = retry_taxonomy or RetryTaxonomy()
        self._policy_explainer = policy_explainer or PolicyExplainer()
        self._outcome_normalizer = outcome_normalizer or OutcomeNormalizer()
        self._retry_executor_policy = retry_executor_policy or RetryExecutorPolicy(max_attempts=2)
        self._operator_handoff_store = operator_handoff_store
        self._scenario_goal_score_engine = scenario_goal_score_engine or ScenarioGoalScoreEngine(base=self._goal_score_engine)
        self._evidence_router = evidence_router or build_evidence_router()
        self._business_memory_service = business_memory_service
        self._business_memory_state_adapter = BusinessMemoryStateAdapter(store=business_memory) if business_memory is not None else None
        self._action_budget_engine = action_budget_engine or ActionBudgetEngine()
        planner_router = _planner_router(capability_aware_planner)
        self._capability_matrix = _canonical_matrix(
            capability_matrix,
            getattr(capability_health_registry, '_matrix', None),
            _router_matrix(execution_capability_router),
            _router_matrix(planner_router),
        )
        registry_store = getattr(capability_health_scoring_service, '_store', None)
        self._capability_health_registry = capability_health_registry or _router_registry(execution_capability_router) or _router_registry(planner_router) or CapabilityHealthRegistry(store=registry_store, matrix=self._capability_matrix)
        if getattr(self._capability_health_registry, '_matrix', None) is not self._capability_matrix:
            self._capability_health_registry = CapabilityHealthRegistry(store=getattr(self._capability_health_registry, '_store', None), matrix=self._capability_matrix, policy=getattr(self._capability_health_registry, '_policy', None))
        router_candidate = execution_capability_router or planner_router
        if router_candidate is not None and _router_matrix(router_candidate) is self._capability_matrix and _router_registry(router_candidate) is self._capability_health_registry:
            self._execution_capability_router = router_candidate
        else:
            self._execution_capability_router = ExecutionCapabilityRouter(matrix=self._capability_matrix, health_registry=self._capability_health_registry)
        if planner_router is self._execution_capability_router:
            self._capability_aware_planner = capability_aware_planner
        else:
            self._capability_aware_planner = CapabilityAwarePlanner(router=self._execution_capability_router)
        self._goal_evaluator = goal_evaluator or GoalEvaluator()
        self._goal_plan_memory_service = goal_plan_memory_service
        self._self_healing_retry_engine = self_healing_retry_engine or SelfHealingRetryEngine()
        self._evidence_persistence_service = evidence_persistence_service or EvidencePersistenceService(
            business_memory_store=business_memory,
            business_memory_service=business_memory_service,
        )
        self._performance_feedback_learning_service = performance_feedback_learning_service
        self._capability_health_scoring_service = capability_health_scoring_service
        self._adaptive_optimization_service = adaptive_optimization_service
        self._multi_goal_planner_service = multi_goal_planner_service
        self._step_builder = step_builder or HeadlessStepBuilder()
        self._operator_handoff_policy = operator_handoff_policy or OperatorHandoffPolicy()
        self._blast_radius_guard = blast_radius_guard or BlastRadiusGuard(action_budget_engine=self._action_budget_engine)
        self._bounded_autonomy_guard = bounded_autonomy_guard or BoundedAutonomyGuard(action_budget_engine=self._action_budget_engine)
        self._safe_self_driving_policy = safe_self_driving_policy or SafeSelfDrivingPolicy()
        self._autonomy_counter_store = autonomy_counter_store
        self._kill_switch_registry = kill_switch_registry
        self._recent_actions_source = recent_actions_source or RecentActionsSource()
        self._decision_keyring = decision_keyring or getattr(decision_core, "_keyring", None) or getattr(getattr(executor, "_guard", None), "_keyring", None)
        self._revenue_outcome_projector = revenue_outcome_projector or RevenueOutcomeProjector()
        self._event_log = event_log
        self._owner_path_service = owner_path_service
        self._autonomy_safety_bundle = autonomy_safety_bundle or AutonomySafetyBundle(
            action_budget_engine=self._action_budget_engine,
            blast_radius_guard=self._blast_radius_guard,
            bounded_autonomy_guard=self._bounded_autonomy_guard,
            safe_self_driving_policy=self._safe_self_driving_policy,
            counter_resolver=AutonomyCounterResolver(store=self._autonomy_counter_store),
            kill_switch_registry=self._kill_switch_registry,
        )
        self._closed_loop_orchestrator = ClosedLoopOrchestrator(
            world_state_updater=WorldStateUpdater(),
            evidence_persistence_service=self._evidence_persistence_service,
            autonomy_policy=AutonomyPolicy(),
            opportunity_detector=OpportunityDetector(),
        )
        self._closed_loop_service = HeadlessClosedLoopService(orchestrator=self._closed_loop_orchestrator)
        self._loop = AutonomyLoop(contract=self)

    def execute_once(self, request: GoalExecutionRequest) -> GoalExecutionReport:
        return self.execute_autopilot(
            GoalExecutionRequest(
                goal=request.goal,
                business_id=request.business_id,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                product_name=request.product_name,
                region=request.region,
                channel=request.channel,
                profile=dict(request.profile),
                signals=list(request.signals),
                constraints=dict(request.constraints),
                economy=dict(request.economy),
                meta=dict(request.meta),
                ceo=request.ceo,
                max_steps=1,
                autonomy_tier=request.autonomy_tier,
                approval_policy=dict(request.approval_policy),
            )
        )

    def execute_autopilot(self, request: GoalExecutionRequest) -> GoalExecutionReport:
        loop_result = self._loop.run(request)
        run_artifact = canonical_goal_execution_report(
            goal=request.goal,
            business_id=request.business_id,
            tenant_id=request.tenant_id,
            completed=loop_result.completed,
            stop_reason=loop_result.stop_reason,
            steps=tuple(loop_result.steps),
            final_feedback=dict(loop_result.final_feedback),
        )
        report = GoalExecutionReport(
            goal=request.goal,
            business_id=request.business_id,
            tenant_id=request.tenant_id,
            completed=loop_result.completed,
            stop_reason=loop_result.stop_reason,
            steps=tuple(loop_result.steps),
            final_feedback=dict(loop_result.final_feedback),
            canonical_run_artifact=run_artifact,
        )
        if self._evidence_persistence_service is not None:
            last_step = loop_result.steps[-1] if loop_result.steps else None
            self._evidence_persistence_service.persist(
                tenant_id=request.tenant_id,
                business_id=request.business_id,
                run_id=loop_result.trace.run_id,
                goal=request.goal,
                step_index=int(last_step.step_index if last_step is not None else max(len(loop_result.steps) - 1, 0)),
                action={
                    "action_type": str(last_step.action if last_step is not None else ""),
                    "action_id": str(last_step.action_id if last_step is not None else ""),
                },
                execution_result=dict(loop_result.final_feedback),
                verification_result=dict(loop_result.final_feedback),
                world_state_before={},
                world_state_after=None,
                request_meta=dict(request.meta),
                request_profile=dict(request.profile),
                request_constraints=dict(request.constraints),
                request_signals=list(request.signals),
                request_channel=request.channel,
                request_region=request.region,
                request_product_name=request.product_name,
                completed=loop_result.completed,
                stop_reason=loop_result.stop_reason,
                final_feedback=dict(loop_result.final_feedback),
                step_count=len(loop_result.steps),
            )
        if self._ledger is not None:
            self._ledger.write(
                LedgerRecord(
                    run_id=loop_result.trace.run_id,
                    trace_id=loop_result.trace.trace_id,
                    business_id=request.business_id,
                    tenant_id=request.tenant_id,
                    goal=request.goal,
                    completed=loop_result.completed,
                    stop_reason=loop_result.stop_reason,
                    steps_count=len(loop_result.steps),
                    final_feedback=dict(loop_result.final_feedback),
                    trace=loop_result.trace.to_dict(),
                    canonical_run_artifact=run_artifact,
                )
            )
        return report


__all__ = [
    "CANON_HEADLESS_EXECUTION_CONTRACT",
    "CEOParticipation",
    "GoalExecutionRequest",
    "GoalExecutionReport",
    "GoalExecutionStep",
    "HeadlessExecutionContract",
]
