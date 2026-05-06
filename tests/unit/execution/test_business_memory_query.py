from __future__ import annotations

from execution.business_memory_query import BusinessMemoryQueryService
from execution.business_operating_memory import FileBusinessOperatingMemoryStore


def test_business_memory_query_service_reads_summary_and_lists(tmp_path) -> None:
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")
    store.remember_execution(
        tenant_id="tenant-1",
        business_id="biz-1",
        run_id="run-1",
        goal="increase revenue",
        completed=False,
        stop_reason="execution_failed",
        final_feedback={"goal_score": 0.25, "error": "timeout"},
        step_count=1,
        profile={"segment": "services"},
        constraints={"budget_limit": "1000"},
        signals=[{"type": "lead_volume", "name": "weekly", "value": "low"}],
        meta={"channel": "headless", "region": "eu"},
        channel="headless",
        region="eu",
        product_name="BusinesAIOS",
        recorded_at="2026-03-21T10:00:00Z",
    )
    store.remember_execution(
        tenant_id="tenant-1",
        business_id="biz-1",
        run_id="run-2",
        goal="increase revenue",
        completed=True,
        stop_reason="goal_reached",
        final_feedback={"goal_score": 0.85, "goal_reached": True},
        step_count=2,
        profile={"segment": "services"},
        constraints={"budget_limit": "1200"},
        signals=[{"type": "lead_volume", "name": "weekly", "value": "high"}],
        meta={"channel": "headless", "region": "eu"},
        channel="headless",
        region="eu",
        product_name="BusinesAIOS",
        recorded_at="2026-03-21T11:00:00Z",
    )

    query = BusinessMemoryQueryService(store=store)
    summary = query.get_summary(tenant_id="tenant-1", business_id="biz-1")
    recent = query.get_recent_runs(tenant_id="tenant-1", business_id="biz-1", limit=10)
    failures = query.get_recurring_failures(tenant_id="tenant-1", business_id="biz-1")
    wins = query.get_recurring_wins(tenant_id="tenant-1", business_id="biz-1")

    assert summary["total_runs"] == 2
    assert summary["business_profile"] == {"segment": "services", "channel": "headless", "region": "eu"}
    assert summary["completed_runs"] == 1
    assert recent[0]["run_id"] == "run-2"
    assert failures[0]["key"] == "timeout"
    assert wins[0]["key"] == "goal_reached"


def test_business_memory_query_service_clamps_non_positive_limit(tmp_path) -> None:
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")
    store.remember_execution(
        tenant_id="tenant-1",
        business_id="biz-1",
        run_id="run-1",
        goal="increase revenue",
        completed=True,
        stop_reason="goal_reached",
        final_feedback={"goal_score": 0.8, "goal_reached": True},
        step_count=1,
        profile={},
        constraints={},
        signals=[],
        meta={},
        channel="headless",
        region="eu",
        product_name="BusinesAIOS",
    )
    query = BusinessMemoryQueryService(store=store)
    assert query.get_recent_runs(tenant_id="tenant-1", business_id="biz-1", limit=0) == []
