from __future__ import annotations

import pytest


budget_mod = pytest.importorskip("execution.action_budget_engine")
perf_mod = pytest.importorskip("execution.performance_feedback_learning")

ActionBudgetEngine = budget_mod.ActionBudgetEngine
PerformanceFeedbackLearningService = perf_mod.PerformanceFeedbackLearningService
FilePerformanceFeedbackStore = perf_mod.FilePerformanceFeedbackStore


def test_performance_learning_can_tighten_budget_posture_for_future_runs(tmp_path) -> None:
    service = PerformanceFeedbackLearningService(
        store=FilePerformanceFeedbackStore(root_dir=tmp_path / "performance")
    )
    engine = ActionBudgetEngine()

    for _ in range(4):
        service.update_after_step(
            tenant_id="tenant-1",
            business_id="biz-1",
            goal="increase revenue",
            feedback={
                "executed": False,
                "verified": False,
                "action_budget": {
                    "snapshot_after": {
                        "spent_total": 25.0,
                        "budget_change_total": 0.0,
                        "outbound_total": 0,
                        "publications_total": 0,
                    }
                },
            },
        )

    performance_context = service.load_context(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal="increase revenue",
    )

    class _Request:
        economy = {"max_run_cost": 10.0, "max_total_cost": 20.0}
        constraints = {}
        meta = {"performance_learning": performance_context}

    decision = engine.evaluate(
        request=_Request(),
        action_type="launch_campaign",
        payload={"estimated_cost": 9.0},
        previous_feedback={"action_budget_state": {}},
    )

    assert performance_context["recommended_budget_posture"] in {"neutral", "tighten"}
    if performance_context["recommended_budget_posture"] == "tighten":
        assert decision.allowed is False


def test_performance_learning_exposes_cost_efficiency_signal(tmp_path) -> None:
    service = PerformanceFeedbackLearningService(
        store=FilePerformanceFeedbackStore(root_dir=tmp_path / "performance")
    )

    service.update_after_step(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal="increase revenue",
        feedback={
            "executed": True,
            "verified": True,
            "goal_evaluation": {"achieved": True},
            "action_budget": {
                "snapshot_after": {
                    "spent_total": 1.0,
                    "budget_change_total": 0.0,
                    "outbound_total": 1,
                    "publications_total": 0,
                }
            },
        },
    )

    context = service.load_context(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal="increase revenue",
    )

    assert "cost_efficiency_score" in context
    assert 0.0 <= context["cost_efficiency_score"] <= 1.0


def test_performance_learning_records_retry_signals_without_second_brain_semantics(tmp_path) -> None:
    service = PerformanceFeedbackLearningService(
        store=FilePerformanceFeedbackStore(root_dir=tmp_path / "performance")
    )

    context = service.update_after_step(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal="increase revenue",
        feedback={
            "executed": False,
            "verified": False,
            "self_healing_retry": {
                "reason": "critical_recurring_failure_pattern",
                "should_open_operator_handoff": "true",
                "should_quarantine_capability": "true",
                "cooldown_seconds": 45,
                "recovery_mode": "cooldown_then_operator_review",
                "error_family": "rate_limit",
            },
        },
    )

    assert "retry_observed" in context["recent_signals"]
    assert "retry_cooldown" in context["recent_signals"]
    assert "retry_operator_handoff" in context["recent_signals"]
    assert "retry_quarantine_signal" in context["recent_signals"]
    assert any(item.startswith("retry_family:rate_limit") for item in context["recent_signals"])
    assert len(context["recent_signals"]) <= 20
