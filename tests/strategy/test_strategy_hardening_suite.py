from __future__ import annotations
from execution.multi_goal_planner import FileMultiGoalPlannerStore, MultiGoalPlannerService
from execution.strategy.planner_state_contract import StrategicGoalRecord
from execution.strategy.portfolio_allocator import PortfolioAllocator
from execution.strategy.planner_memory import PlannerMemory
def _record(*, goal_id: str, planning_memory: dict, priority: int = 70, urgency: int = 70) -> StrategicGoalRecord:
    return StrategicGoalRecord(
        goal_id=goal_id,
        goal=goal_id,
        priority=priority,
        urgency=urgency,
        budget_weight=1.0,
        status='queued',
        blocked=False,
        progress_score=0.1,
        planning_horizon='week',
        metadata={'dependency_analysis': {'dependency_ready': True, 'missing_dependencies': [], 'downstream_goal_ids': []}},
        planning_memory=planning_memory,
    )
def test_strategy_suite_preserves_dependency_and_memory_truth(tmp_path) -> None:
    store = FileMultiGoalPlannerStore(root_dir=tmp_path)
    service = MultiGoalPlannerService(store=store)
    service.add_goal(tenant_id='t', business_id='b', goal_id='grow', goal='Grow revenue', priority=90, urgency=90)
    service.add_goal(tenant_id='t', business_id='b', goal_id='launch', goal='Launch campaign', priority=95, urgency=95, metadata={'depends_on': ['grow']})
    selection = service.select_next_goal(tenant_id='t', business_id='b')
    context = service.load_context(tenant_id='t', business_id='b')
    assert selection.selected_goal_id == 'grow'
    assert 'launch' in context['strategy_diagnostics']['dependency_graph']['blocked_goal_ids']
    memory = PlannerMemory()
    updated = memory.apply_feedback(metadata={}, feedback_view={'next_mode': 'continue', 'completion_ratio': 0.8, 'achieved': True}, feedback={'verification_status': 'verified', 'economic': {'cost': 8.0, 'revenue_delta': 24.0}, 'strategy_advisory': {'preferred_route_key': 'crm.update', 'preferred_routes': ['crm.update'], 'focus_mode': 'scale_verified_route'}})
    updated = memory.apply_feedback(metadata=updated, feedback_view={'next_mode': 'continue', 'completion_ratio': 0.9, 'achieved': True}, feedback={'verification_status': 'verified', 'economic': {'cost': 6.0, 'revenue_delta': 26.0}, 'strategy_advisory': {'preferred_route_key': 'crm.update', 'preferred_routes': ['crm.update'], 'focus_mode': 'scale_verified_route'}})
    summary = memory.summarize_metadata(metadata=updated)
    assert summary.verified_success_streak >= 2
    assert summary.route_stability_score > 0.5
def test_strategy_suite_prefers_verified_and_ready_paths() -> None:
    allocator = PortfolioAllocator()
    strong = _record(goal_id='strong', planning_memory={'economic_signal_peak': 1.0, 'spend_pressure_peak': 0.2, 'route_confidence_peak': 0.8, 'route_stability_score': 0.9, 'focus_mode_stability_score': 0.8, 'verified_success_streak': 3, 'last_focus_mode': 'scale_verified_route', 'stalled_runs': 0, 'blocked_runs': 0})
    weak = _record(goal_id='weak', planning_memory={'economic_signal_peak': -0.4, 'spend_pressure_peak': 0.9, 'route_confidence_peak': 0.0, 'route_stability_score': 0.1, 'focus_mode_stability_score': 0.1, 'verified_success_streak': 0, 'last_focus_mode': 'retry_carefully', 'stalled_runs': 4, 'blocked_runs': 2})
    blocked = StrategicGoalRecord(goal_id='blocked', goal='blocked', priority=90, urgency=90, budget_weight=1.1, status='queued', blocked=False, progress_score=0.0, planning_horizon='today', dependencies=('strong',), metadata={'dependency_analysis': {'dependency_ready': False, 'missing_dependencies': ['strong'], 'downstream_goal_ids': []}}, planning_memory={'economic_signal_peak': 1.0, 'route_confidence_peak': 1.0, 'last_focus_mode': 'scale_verified_route'})
    assert allocator.advisory_score(record=strong, base_score=70.0) > allocator.advisory_score(record=weak, base_score=70.0)
    assert allocator.advisory_score(record=strong, base_score=60.0) > allocator.advisory_score(record=blocked, base_score=85.0)
