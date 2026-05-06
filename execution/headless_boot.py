from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from execution.blast_radius_guard import BlastRadiusGuard
from execution.autonomy_counters import AutonomyCounterResolver, FileAutonomyCounterStore
from execution.autonomy_kill_switch import FileAutonomyKillSwitchRegistry
from application.autonomy.autonomy_safety_bundle import AutonomySafetyBundle
from application.memory.business_memory_query import BusinessMemoryQueryService
from application.memory.business_memory_state_adapter import BusinessMemoryStateAdapter
from application.memory.business_operating_memory import BusinessMemoryCompactor, BusinessMemoryPolicy, FileBusinessOperatingMemoryStore
from application.effects.effect_journal import FileEffectJournal
from execution.goal_score import GoalScoreEngine
from application.planning.long_horizon_planner import LongHorizonPlanner
from application.planning.multi_goal_planner import FileMultiGoalPlannerStore, MultiGoalPlannerService
from execution.performance_feedback_learning import FilePerformanceFeedbackStore, PerformanceFeedbackLearningService
from application.planning.strategy_memory import FileStrategyMemoryStore, StrategyMemoryService
from application.headless.contract import HeadlessExecutionContract
from application.headless.feedback import SimpleHeadlessFeedbackReader
from application.headless.goal_mapper import HeadlessGoalStateMapper
from execution.headless_ledger import FileHeadlessLedger
from execution.headless_paths import build_headless_runtime_paths
from execution.headless_state_store import FileHeadlessStateStore
from application.headless.stop_policy import HeadlessStopPolicy
from execution.idempotency_guard import FileIdempotencyGuard
from execution.operator_handoff import FileOperatorHandoffStore
from execution.outcome_normalizer import OutcomeNormalizer
from execution.revenue_outcome import RevenueOutcomeProjector
from execution.policy_explainer import PolicyExplainer
from execution.optimization.adaptive_optimization_service import AdaptiveOptimizationService
from execution.optimization.adaptive_optimizer import AdaptiveOptimizer
from execution.optimization.performance_profile_store import FilePerformanceProfileStore
from execution.owner_path import FileOwnerPathStore, OwnerPathService
from execution.retry_executor_policy import RetryExecutorPolicy
from application.learning.retry_learning_engine import RetryLearningEngine
from application.learning.retry_learning_store import RetryLearningStore
from execution.self_healing_retry import SelfHealingRetryEngine
from application.learning.retry_taxonomy import RetryTaxonomy
from execution.scenario_goal_score import ScenarioGoalScoreEngine
from bootstrap.entrypoint_context import bootstrap_entrypoint, is_allowed_bootstrap_entrypoint
from runtime.boot.system_builder import build_system
from runtime.platform.business_memory.service import BusinessMemoryService
from core.safety.operational.runtime_bootstrap import resolve_operational_safety_runtime
from runtime.platform.business_memory.store import FileBusinessMemoryStore


CANON_HEADLESS_BOOT = True


@dataclass(frozen=True)
class HeadlessRuntime:
    decision_core: object
    executor: object
    contract: HeadlessExecutionContract
    ledger: FileHeadlessLedger
    business_memory: FileBusinessOperatingMemoryStore
    business_memory_query: BusinessMemoryQueryService
    state_store: FileHeadlessStateStore
    effect_journal: FileEffectJournal
    idempotency_guard: FileIdempotencyGuard
    operator_handoff_store: FileOperatorHandoffStore
    business_memory_service: BusinessMemoryService
    blast_radius_guard: object | None = None
    decision_keyring: object | None = None
    revenue_outcome_projector: object | None = None
    event_log: object | None = None
    operational_budget_service: object | None = None
    autonomy_counter_store: object | None = None
    kill_switch_registry: object | None = None
    autonomy_safety_bundle: object | None = None
    adaptive_optimization_service: object | None = None
    owner_path_service: object | None = None
    performance_feedback_learning_service: object | None = None
    self_healing_retry_engine: object | None = None
    multi_goal_planner_service: object | None = None


@lru_cache(maxsize=8)
def build_headless_runtime(*, entrypoint: str = "headless_sdk", root_dir: str | Path | None = None) -> HeadlessRuntime:
    name = str(entrypoint).strip() or "headless_sdk"
    if not is_allowed_bootstrap_entrypoint(name):
        raise ValueError(f"UNKNOWN_BOOTSTRAP_ENTRYPOINT:{name}")
    with bootstrap_entrypoint(name):
        core, executor, event_log, event_store, payment_outbox, stack, learning_job = build_system()
    del event_store, payment_outbox, stack, learning_job
    paths = build_headless_runtime_paths(root_dir=root_dir)
    ledger = FileHeadlessLedger(root_dir=paths.headless_ledger_dir)
    memory_policy = BusinessMemoryPolicy()
    business_memory = FileBusinessOperatingMemoryStore(
        root_dir=paths.business_operating_memory_dir,
        policy=memory_policy,
        compactor=BusinessMemoryCompactor(policy=memory_policy),
    )
    business_memory_query = BusinessMemoryQueryService(store=business_memory)
    state_store = FileHeadlessStateStore(root_dir=paths.headless_state_dir)
    effect_journal = FileEffectJournal(root_dir=paths.headless_effects_dir)
    idempotency_guard = FileIdempotencyGuard(root_dir=paths.headless_idempotency_dir)
    operator_handoff_store = FileOperatorHandoffStore(root_dir=paths.headless_operator_handoff_dir)
    business_memory_service = BusinessMemoryService(
        store=FileBusinessMemoryStore(root_dir=paths.business_memory_dir),
    )
    autonomy_counter_store = FileAutonomyCounterStore(root_dir=paths.autonomy_counters_dir)
    kill_switch_registry = FileAutonomyKillSwitchRegistry(root_dir=paths.autonomy_kill_switch_dir)
    goal_score_engine = GoalScoreEngine()
    blast_radius_guard = BlastRadiusGuard()
    revenue_outcome_projector = RevenueOutcomeProjector()
    autonomy_safety_bundle = AutonomySafetyBundle(
        blast_radius_guard=blast_radius_guard,
        counter_resolver=AutonomyCounterResolver(store=autonomy_counter_store),
        kill_switch_registry=kill_switch_registry,
    )
    adaptive_optimization_service = AdaptiveOptimizationService(
        optimizer=AdaptiveOptimizer(
            store=FilePerformanceProfileStore(root_dir=paths.adaptive_optimization_dir)
        )
    )
    owner_path_service = OwnerPathService(
        store=FileOwnerPathStore(root_dir=paths.owner_path_dir)
    )
    strategy_memory_service = StrategyMemoryService(
        store=FileStrategyMemoryStore(root_dir=paths.strategy_memory_dir)
    )
    long_horizon_planner = LongHorizonPlanner(strategy_memory=strategy_memory_service)
    performance_feedback_learning_service = PerformanceFeedbackLearningService(
        store=FilePerformanceFeedbackStore(root_dir=paths.performance_learning_dir)
    )
    multi_goal_planner_service = MultiGoalPlannerService(
        store=FileMultiGoalPlannerStore(root_dir=paths.multi_goal_planner_dir),
        long_horizon_planner=long_horizon_planner,
    )
    retry_learning_store = RetryLearningStore(root_dir=paths.retry_learning_dir)
    self_healing_retry_engine = SelfHealingRetryEngine(
        learning_store=retry_learning_store,
        retry_learning_engine=RetryLearningEngine(learning_store=retry_learning_store),
    )
    operational_runtime = resolve_operational_safety_runtime(default_root=paths.root_dir)
    if getattr(executor, "_operational_budget_service", None) is None:
        executor._operational_budget_service = operational_runtime.service
    executor._autonomy_safety_bundle = autonomy_safety_bundle
    contract = HeadlessExecutionContract(
        decision_core=core,
        executor=executor,
        state_mapper=HeadlessGoalStateMapper(business_memory_state_adapter=BusinessMemoryStateAdapter(store=business_memory, policy=memory_policy)),
        feedback_reader=SimpleHeadlessFeedbackReader.default(),
        stop_policy=HeadlessStopPolicy(max_failures=1),
        ledger=ledger,
        business_memory=business_memory,
        state_store=state_store,
        effect_journal=effect_journal,
        idempotency_guard=idempotency_guard,
        goal_score_engine=goal_score_engine,
        retry_taxonomy=RetryTaxonomy(),
        policy_explainer=PolicyExplainer(),
        outcome_normalizer=OutcomeNormalizer(),
        retry_executor_policy=RetryExecutorPolicy(max_attempts=2),
        operator_handoff_store=operator_handoff_store,
        scenario_goal_score_engine=ScenarioGoalScoreEngine(base=goal_score_engine),
        business_memory_service=business_memory_service,
        adaptive_optimization_service=adaptive_optimization_service,
        blast_radius_guard=blast_radius_guard,
        decision_keyring=getattr(core, "_keyring", None) or getattr(getattr(executor, "_guard", None), "_keyring", None),
        revenue_outcome_projector=revenue_outcome_projector,
        event_log=event_log,
        autonomy_counter_store=autonomy_counter_store,
        kill_switch_registry=kill_switch_registry,
        autonomy_safety_bundle=autonomy_safety_bundle,
        owner_path_service=owner_path_service,
        performance_feedback_learning_service=performance_feedback_learning_service,
        self_healing_retry_engine=self_healing_retry_engine,
        multi_goal_planner_service=multi_goal_planner_service,
    )
    return HeadlessRuntime(
        decision_core=core,
        executor=executor,
        contract=contract,
        ledger=ledger,
        business_memory=business_memory,
        business_memory_query=business_memory_query,
        state_store=state_store,
        effect_journal=effect_journal,
        idempotency_guard=idempotency_guard,
        operator_handoff_store=operator_handoff_store,
        business_memory_service=business_memory_service,
        adaptive_optimization_service=adaptive_optimization_service,
        blast_radius_guard=blast_radius_guard,
        decision_keyring=getattr(core, "_keyring", None) or getattr(getattr(executor, "_guard", None), "_keyring", None),
        revenue_outcome_projector=revenue_outcome_projector,
        event_log=event_log,
        autonomy_counter_store=autonomy_counter_store,
        kill_switch_registry=kill_switch_registry,
        autonomy_safety_bundle=autonomy_safety_bundle,
        owner_path_service=owner_path_service,
        performance_feedback_learning_service=performance_feedback_learning_service,
        self_healing_retry_engine=self_healing_retry_engine,
        multi_goal_planner_service=multi_goal_planner_service,
    )


__all__ = ["CANON_HEADLESS_BOOT", "HeadlessRuntime", "build_headless_runtime"]
