from __future__ import annotations

from pathlib import Path

from execution.goal_plan_memory import FileGoalPlanMemoryStore, GoalPlanMemoryService


def test_goal_plan_memory_persists_steps_across_runs(tmp_path: Path) -> None:
    service = GoalPlanMemoryService(store=FileGoalPlanMemoryStore(root_dir=tmp_path / "goal_plans"))
    updated = service.update_after_step(tenant_id="tenant-1", business_id="biz-1", goal="increase revenue", step_index=0, action_type="launch_campaign", feedback={"verification_status": "verified", "verified": True, "goal_reached": False, "goal_evaluation": {"reason": "continue"}})
    reloaded = service.load_context(tenant_id="tenant-1", business_id="biz-1", goal="increase revenue")
    assert updated["plan_id"] == reloaded["plan_id"]
    assert len(reloaded["completed_steps"]) == 1
    assert reloaded["completed_steps"][0]["action_type"] == "launch_campaign"
