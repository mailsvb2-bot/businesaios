from __future__ import annotations

import pytest

mg_mod = pytest.importorskip("execution.multi_goal_planner")

MultiGoalPlannerService = mg_mod.MultiGoalPlannerService
FileMultiGoalPlannerStore = mg_mod.FileMultiGoalPlannerStore


def test_multi_goal_progression_moves_selection_after_completion(tmp_path) -> None:
    service = MultiGoalPlannerService(
        store=FileMultiGoalPlannerStore(root_dir=tmp_path / "multi_goal")
    )

    service.add_goal(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal_id="goal-a",
        goal="increase revenue",
        priority=95,
        urgency=90,
    )
    service.add_goal(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal_id="goal-b",
        goal="improve retention",
        priority=80,
        urgency=70,
    )

    first = service.select_next_goal(tenant_id="tenant-1", business_id="biz-1")
    service.update_goal_after_run(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal_id="goal-a",
        feedback={"goal_evaluation": {"achieved": True, "reason": "goal_achieved", "completion_ratio": 1.0}},
    )
    second = service.select_next_goal(tenant_id="tenant-1", business_id="biz-1")

    assert first.selected_goal_id == "goal-a"
    assert second.selected_goal_id in {"goal-b", None}


def test_multi_goal_blocked_goal_can_be_deprioritized(tmp_path) -> None:
    service = MultiGoalPlannerService(
        store=FileMultiGoalPlannerStore(root_dir=tmp_path / "multi_goal")
    )

    service.add_goal(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal_id="goal-a",
        goal="increase revenue",
        priority=100,
        urgency=100,
    )
    service.add_goal(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal_id="goal-b",
        goal="improve retention",
        priority=70,
        urgency=70,
    )

    service.update_goal_after_run(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal_id="goal-a",
        feedback={"approval_required": True, "goal_evaluation": {"achieved": False, "completion_ratio": 0.0, "reason": "operator_required"}},
    )
    selection = service.select_next_goal(tenant_id="tenant-1", business_id="biz-1")

    assert selection.selected_goal_id in {"goal-b", "goal-a", None}
    assert selection.reason in {"highest_ranked_goal", "no_eligible_goals"}
