from __future__ import annotations

from interfaces.api.business_memory_models import (
    BusinessMemoryGetRequest,
    BusinessMemoryRecentRunsRequest,
    BusinessMemorySummaryRequest,
)
from interfaces.api.business_memory_route_handlers import BusinessMemoryRouteHandlers


def test_business_memory_route_handlers_delegate_to_query(monkeypatch):
    class StubQuery:
        def get_memory(self, *, tenant_id, business_id):
            return {"tenant_id": tenant_id, "business_id": business_id, "total_runs": 2}

        def get_summary(self, *, tenant_id, business_id):
            return {
                "tenant_id": tenant_id,
                "business_id": business_id,
                "total_runs": 2,
                "completed_runs": 1,
                "failed_runs": 1,
                "average_goal_score": 0.55,
                "active_goals": ["increase revenue"],
                "learned_preferences": {"channel": "headless"},
                "recurring_failures": ["timeout"],
                "recurring_wins": ["goal_reached"],
            }

        def get_recent_runs(self, *, tenant_id, business_id, limit):
            return [{"run_id": "run-2", "goal": "increase revenue", "completed": True}][:limit]

    class StubRuntime:
        business_memory_query = StubQuery()

    monkeypatch.setattr("interfaces.api.business_memory_route_handlers.build_headless_runtime", lambda: StubRuntime())

    handlers = BusinessMemoryRouteHandlers()
    full = handlers.get_memory(BusinessMemoryGetRequest(tenant_id="tenant-1", business_id="biz-1"))
    assert full.payload["total_runs"] == 2

    summary = handlers.get_summary(BusinessMemorySummaryRequest(tenant_id="tenant-1", business_id="biz-1"))
    assert summary.total_runs == 2
    assert summary.recurring_failures == ["timeout"]

    recent = handlers.get_recent_runs(BusinessMemoryRecentRunsRequest(tenant_id="tenant-1", business_id="biz-1", limit=5))
    assert recent.runs[0]["run_id"] == "run-2"



def test_business_memory_route_handlers_expose_patterns(monkeypatch):
    class StubQuery:
        def get_recurring_failures(self, *, tenant_id, business_id):
            return [{"key": "timeout", "count": 2}]

        def get_recurring_wins(self, *, tenant_id, business_id):
            return [{"key": "goal_reached", "count": 3}]

    class StubRuntime:
        business_memory_query = StubQuery()

    monkeypatch.setattr(
        "interfaces.api.business_memory_route_handlers.build_headless_runtime",
        lambda: StubRuntime(),
    )

    handlers = BusinessMemoryRouteHandlers()
    failures = handlers.get_failures(BusinessMemorySummaryRequest(tenant_id="tenant-1", business_id="biz-1"))
    wins = handlers.get_wins(BusinessMemorySummaryRequest(tenant_id="tenant-1", business_id="biz-1"))
    assert failures.patterns == [{"key": "timeout", "count": 2}]
    assert wins.patterns == [{"key": "goal_reached", "count": 3}]
