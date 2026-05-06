from __future__ import annotations

import pytest

from execution.capability_health_scoring import CapabilityHealthScoringService, FileCapabilityHealthStore
from execution.multi_goal_planner import FileMultiGoalPlannerStore, MultiGoalPlannerService


def test_capability_health_requires_identity(tmp_path) -> None:
    service = CapabilityHealthScoringService(store=FileCapabilityHealthStore(root_dir=tmp_path / 'health'))
    invalid_tenant_id = str()
    with pytest.raises(ValueError):
        service.update_after_step(tenant_id=invalid_tenant_id, capability_key='launch_campaign', feedback={})


def test_multi_goal_planner_skips_blocked_active_candidate(tmp_path) -> None:
    service = MultiGoalPlannerService(store=FileMultiGoalPlannerStore(root_dir=tmp_path / 'goals'))
    service.add_goal(tenant_id='tenant-1', business_id='biz-1', goal_id='goal-a', goal='increase revenue', priority=100, urgency=100)
    service.add_goal(tenant_id='tenant-1', business_id='biz-1', goal_id='goal-b', goal='improve retention', priority=80, urgency=80)
    service.update_goal_after_run(
        tenant_id='tenant-1',
        business_id='biz-1',
        goal_id='goal-a',
        feedback={'approval_required': True, 'goal_evaluation': {'achieved': False, 'completion_ratio': 0.0, 'reason': 'operator_required'}},
    )
    selection = service.select_next_goal(tenant_id='tenant-1', business_id='biz-1')
    assert selection.selected_goal_id in {'goal-b', None}
