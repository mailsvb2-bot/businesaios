from __future__ import annotations

from execution.multi_goal_planner import FileMultiGoalPlannerStore, MultiGoalPlannerService


def test_multi_goal_capability_penalty_demotes_disabled_goal(tmp_path) -> None:
    service = MultiGoalPlannerService(store=FileMultiGoalPlannerStore(root_dir=tmp_path / 'goals'))
    service.add_goal(
        tenant_id='tenant-1',
        business_id='biz-1',
        goal_id='goal-a',
        goal='reply to lead quickly',
        priority=95,
        urgency=95,
        metadata={'capability': {'runtime': {'enabled': False, 'health_score': 0.0}, 'advisory_flags': {}}},
    )
    service.add_goal(
        tenant_id='tenant-1',
        business_id='biz-1',
        goal_id='goal-b',
        goal='notify owner about lead backlog',
        priority=70,
        urgency=70,
        metadata={'capability': {'runtime': {'enabled': True, 'health_score': 1.0}, 'advisory_flags': {}}},
    )
    selection = service.select_next_goal(tenant_id='tenant-1', business_id='biz-1')
    assert selection.selected_goal_id == 'goal-b'
