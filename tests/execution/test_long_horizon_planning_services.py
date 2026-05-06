from __future__ import annotations

from execution.goal_decomposition_engine import GoalDecompositionEngine
from execution.long_horizon_planner import LongHorizonPlanner
from execution.multi_goal_planner import FileMultiGoalPlannerStore, MultiGoalPlannerService
from execution.performance_feedback_learning import FilePerformanceFeedbackStore, PerformanceFeedbackLearningService
from execution.strategy_memory import FileStrategyMemoryStore, StrategyMemoryService


def test_goal_decomposition_engine_builds_dependency_chain_from_templates() -> None:
    engine = GoalDecompositionEngine()
    result = engine.decompose(goal="increase revenue")
    assert result.goal_family == "revenue_growth"
    assert result.tasks
    assert result.tasks[0].depends_on == ()
    for prev, current in zip(result.tasks, result.tasks[1:]):
        assert current.depends_on == (prev.task_id,)
    assert result.evidence_only is True
    assert result.must_not_issue_decision is True


def test_strategy_memory_stores_compact_feedback_only(tmp_path) -> None:
    service = StrategyMemoryService(store=FileStrategyMemoryStore(root_dir=tmp_path / "strategy"))
    updated = service.update_after_feedback(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal_family="revenue_growth",
        plan_context={"planning_horizon": "week", "tasks": [{"task_id": "t1", "phase": "verify", "estimated_steps": 1}]},
        feedback={
            "verified": True,
            "verification_status": "verified",
            "goal_evaluation": {"achieved": True, "completion_ratio": 1.0},
            "performance_feedback_learning": {"preferred_planning_horizon": "month", "long_horizon_signals": {"checkpoint_readiness": "high"}},
            "huge_raw_payload": {"nested": [1, 2, 3]},
        },
    )
    assert "huge_raw_payload" not in updated["last_compact_feedback"]
    assert updated["preferred_horizon"] == "month"
    assert updated["task_patterns"]["t1"]["verified_runs"] == 1


def test_long_horizon_planner_builds_evidence_only_plan(tmp_path) -> None:
    memory = StrategyMemoryService(store=FileStrategyMemoryStore(root_dir=tmp_path / "strategy"))
    planner = LongHorizonPlanner(strategy_memory=memory)
    plan = planner.build_plan(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal="increase revenue",
        metadata={"planning_horizon": "month"},
        performance_context={"verification_rate": 0.9, "preferred_planning_horizon": "month"},
    ).to_dict()
    assert plan["goal_family"] == "revenue_growth"
    assert plan["planning_horizon"] == "month"
    assert plan["evidence_only"] is True
    assert plan["must_not_issue_decision"] is True
    assert plan["tasks"]


def test_multi_goal_planner_enriches_metadata_with_long_horizon(tmp_path) -> None:
    memory = StrategyMemoryService(store=FileStrategyMemoryStore(root_dir=tmp_path / "strategy"))
    planner = LongHorizonPlanner(strategy_memory=memory)
    service = MultiGoalPlannerService(
        store=FileMultiGoalPlannerStore(root_dir=tmp_path / "goals"),
        long_horizon_planner=planner,
    )
    service.add_goal(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal_id="goal-a",
        goal="increase revenue",
    )
    context = service.load_context(tenant_id="tenant-1", business_id="biz-1")
    assert context["long_horizon"]["goal_family"] == "revenue_growth"
    assert context["long_horizon"]["tasks"]


def test_multi_goal_feedback_updates_strategy_memory(tmp_path) -> None:
    memory = StrategyMemoryService(store=FileStrategyMemoryStore(root_dir=tmp_path / "strategy"))
    planner = LongHorizonPlanner(strategy_memory=memory)
    service = MultiGoalPlannerService(
        store=FileMultiGoalPlannerStore(root_dir=tmp_path / "goals"),
        long_horizon_planner=planner,
    )
    service.add_goal(tenant_id="tenant-1", business_id="biz-1", goal_id="goal-a", goal="increase revenue")
    service.update_goal_after_run(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal_id="goal-a",
        feedback={
            "verified": True,
            "verification_status": "verified",
            "goal_evaluation": {"achieved": True, "completion_ratio": 1.0},
            "performance_feedback_learning": {"preferred_planning_horizon": "month", "long_horizon_signals": {"checkpoint_readiness": "high"}},
        },
    )
    snapshot = memory.load_context(tenant_id="tenant-1", business_id="biz-1", goal_family="revenue_growth")
    assert snapshot["observed_runs"] == 1
    assert snapshot["successful_runs"] == 1
    assert snapshot["decomposition_patterns"]


def test_performance_feedback_learning_exposes_long_horizon_signals(tmp_path) -> None:
    service = PerformanceFeedbackLearningService(store=FilePerformanceFeedbackStore(root_dir=tmp_path / "performance"))
    context = service.update_after_step(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal="increase revenue",
        feedback={
            "executed": True,
            "verified": True,
            "goal_evaluation": {"achieved": True, "completion_ratio": 1.0},
            "action_budget": {"snapshot_after": {"spent_total": 1.0, "budget_change_total": 0.0, "outbound_total": 1, "publications_total": 0}},
        },
    )
    assert context["preferred_planning_horizon"] in {"week", "month"}
    assert context["long_horizon_signals"]["verified"] is True
    assert context["evidence_only"] is True
