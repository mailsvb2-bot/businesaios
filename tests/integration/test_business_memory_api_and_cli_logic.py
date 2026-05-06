from __future__ import annotations

from execution.business_operating_memory import FileBusinessOperatingMemoryStore
from interfaces.api.business_memory_models import BusinessMemoryGetRequest, BusinessMemorySummaryRequest
from interfaces.api.business_memory_route_handlers import BusinessMemoryRouteHandlers
from interfaces.cli.business_memory_tools import main


def test_business_memory_read_surfaces_are_consistent(monkeypatch, tmp_path) -> None:
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")
    store.remember_execution(
        tenant_id="tenant-1",
        business_id="biz-1",
        run_id="run-1",
        goal="grow pipeline",
        completed=True,
        stop_reason="goal_reached",
        final_feedback={"goal_score": 0.9, "goal_reached": True},
        step_count=1,
        profile={"segment": "services"},
        constraints={},
        signals=[],
        meta={"channel": "headless", "region": "eu"},
        channel="headless",
        region="eu",
        product_name="BusinesAIOS",
        recorded_at="2026-03-21T12:00:00Z",
    )

    class StubRuntime:
        def __init__(self, query):
            self.business_memory_query = query

    runtime = StubRuntime(None)
    from execution.business_memory_query import BusinessMemoryQueryService
    runtime.business_memory_query = BusinessMemoryQueryService(store=store)

    monkeypatch.setattr("interfaces.api.business_memory_route_handlers.build_headless_runtime", lambda: runtime)
    monkeypatch.setattr("interfaces.cli.business_memory_tools.build_headless_runtime", lambda: runtime)

    handlers = BusinessMemoryRouteHandlers()
    full = handlers.get_memory(BusinessMemoryGetRequest(tenant_id="tenant-1", business_id="biz-1"))
    summary = handlers.get_summary(BusinessMemorySummaryRequest(tenant_id="tenant-1", business_id="biz-1"))

    assert full.payload["tenant_id"] == "tenant-1"
    assert summary.total_runs == 1
    assert main(["summary", "--tenant-id", "tenant-1", "--business-id", "biz-1"]) == 0



def test_business_memory_cli_rejects_non_positive_limit(monkeypatch, capsys) -> None:
    from interfaces.cli import business_memory_tools as cli

    class StubRuntime:
        business_memory_query = object()

    monkeypatch.setattr(cli, "build_headless_runtime", lambda: StubRuntime())
    try:
        cli.main(["recent-runs", "--tenant-id", "t1", "--business-id", "b1", "--limit", "0"])
    except SystemExit as exc:
        assert str(exc) == "--limit must be >= 1"
    else:
        raise AssertionError("expected SystemExit for invalid limit")


def test_business_memory_read_surfaces_include_pattern_views(monkeypatch) -> None:
    class StubQuery:
        def get_memory(self, *, tenant_id, business_id):
            return {"tenant_id": tenant_id, "business_id": business_id}

        def get_summary(self, *, tenant_id, business_id):
            return {"tenant_id": tenant_id, "business_id": business_id, "total_runs": 1, "completed_runs": 1, "failed_runs": 0, "average_goal_score": 1.0, "active_goals": [], "learned_preferences": {}, "recurring_failures": [], "recurring_wins": ["goal_reached"]}

        def get_recurring_failures(self, *, tenant_id, business_id):
            return [{"key": "timeout", "count": 2}]

        def get_recurring_wins(self, *, tenant_id, business_id):
            return [{"key": "goal_reached", "count": 3}]

    class StubRuntime:
        business_memory_query = StubQuery()

    monkeypatch.setattr("interfaces.api.business_memory_route_handlers.build_headless_runtime", lambda: StubRuntime())

    handlers = BusinessMemoryRouteHandlers()
    failures = handlers.get_failures(BusinessMemorySummaryRequest(tenant_id="tenant-1", business_id="biz-1"))
    wins = handlers.get_wins(BusinessMemorySummaryRequest(tenant_id="tenant-1", business_id="biz-1"))
    assert failures.patterns[0]["key"] == "timeout"
    assert wins.patterns[0]["key"] == "goal_reached"
