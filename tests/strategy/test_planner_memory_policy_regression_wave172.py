from execution.strategy.planner_memory import PlannerMemory


def test_planner_memory_tolerates_malformed_metadata_and_preserves_policy_bounds():
    memory = PlannerMemory()
    summary = memory.summarize_metadata(metadata={"planning_memory": {"observed_runs": "bad", "successful_runs": None, "blocked_runs": "7x", "verified_success_streak": "oops"}})
    assert summary.observed_runs == 0
    assert summary.successful_runs == 0
    assert summary.blocked_runs == 0
    assert summary.verified_success_streak == 0


def test_planner_memory_uses_policy_for_route_confidence_and_stability():
    memory = PlannerMemory()
    updated = memory.apply_feedback(
        metadata={"planning_memory": {"last_preferred_route_key": "ads", "last_focus_mode": "scale"}},
        feedback_view={"next_mode": "continue", "completion_ratio": 0.3, "achieved": True},
        feedback={"adaptive_optimization": {"strategy_advisory": {"preferred_route_key": "ads", "preferred_routes": ["ads", "email"], "focus_mode": "scale"}}, "verification_status": "verified"},
    )
    planning_memory = updated["planning_memory"]
    assert planning_memory["route_confidence_peak"] == 0.8
    assert planning_memory["route_stability_score"] == 0.73
    assert round(planning_memory["focus_mode_stability_score"], 2) == 0.58
