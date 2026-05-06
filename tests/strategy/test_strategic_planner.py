from __future__ import annotations

from types import SimpleNamespace

from execution.strategy import StrategicPlanner


def test_strategic_planner_builds_horizon_and_focus_from_goal_text() -> None:
    planner = StrategicPlanner()
    item = SimpleNamespace(
        goal_id='goal-revenue',
        goal='Increase revenue this quarter',
        priority=90,
        urgency=70,
        budget_weight=1.2,
        status='queued',
        blocked=False,
        progress_score=0.0,
        metadata={},
    )
    record = planner.build_record(item=item)
    assert record.planning_horizon == 'quarter'
    assert 'quarter' in record.strategy_tags
    assert record.metadata['decomposed_focus']


def test_strategic_planner_explains_deferred_and_blocked_goals() -> None:
    planner = StrategicPlanner()
    ranked = [
        SimpleNamespace(goal_id='g1', goal='Increase revenue', priority=100, urgency=100, budget_weight=1.0, status='queued', blocked=False, progress_score=0.1, metadata={}),
        SimpleNamespace(goal_id='g2', goal='Improve retention', priority=80, urgency=80, budget_weight=1.0, status='queued', blocked=False, progress_score=0.0, metadata={'dependencies': ['g1']}),
        SimpleNamespace(goal_id='g3', goal='Collect reviews', priority=60, urgency=60, budget_weight=1.0, status='blocked', blocked=True, progress_score=0.0, metadata={}),
    ]
    context = planner.explain_selection(selected_item=ranked[0], ranked_items=ranked)
    assert context.selected_goal_id == 'g1'
    assert 'g3' in context.blocked_goal_ids
    assert 'g2' in context.deferred_goal_ids
    assert context.diagnostics['dependency_blocked_goal_ids'] == ['g2']


def test_strategic_planner_exposes_planning_memory_summary() -> None:
    planner = StrategicPlanner()
    ranked = [
        SimpleNamespace(goal_id='g1', goal='Increase revenue', priority=100, urgency=100, budget_weight=1.0, status='queued', blocked=False, progress_score=0.4, metadata={
            'planning_memory': {
                'observed_runs': 3,
                'successful_runs': 1,
                'stalled_runs': 2,
                'completion_ratio_peak': 0.6,
                'last_next_mode': 'continue',
                'recent_modes': ['replan', 'continue'],
                'evidence_only': True,
                'must_not_issue_decision': True,
            }
        }),
    ]
    context = planner.explain_selection(selected_item=ranked[0], ranked_items=ranked)
    assert context.planning_memory_summary['observed_runs'] == 3
    assert context.planning_memory_summary['last_next_mode'] == 'continue'
