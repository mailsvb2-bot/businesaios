from __future__ import annotations
from interfaces.api.governance_advanced_models import BusinessMemoryGovernanceSummaryRequest, DriftTrendRequest, PromoteScenarioBaselineRequest, RollbackTimelineRequest
from interfaces.api.governance_advanced_route_handlers import GovernanceAdvancedRouteHandlers

class StubGovernance:
    def promote_best_for_scenario(self, **kwargs): return {"baseline_name":"scenario/golden","source_run_id":"run-1","goal":"grow","business_id":"biz-1","tenant_id":"tenant-1","promoted_at_label":kwargs["label"],"metadata":{"via":"api"}}
    def rollback_timeline(self, *, baseline_name: str) -> str: return f"timeline:{baseline_name}"
    def drift_trend(self, **kwargs): return {"baseline_name":kwargs["baseline_name"],"samples":2,"avg_goal_score_delta":-0.2,"high_count":1,"medium_count":1,"low_count":0,"none_count":0,"summary":"degrading"}
    def memory_summary(self, **kwargs): return {"tenant_id":kwargs["tenant_id"],"business_id":kwargs["business_id"],"total_runs":3,"completed_runs":1,"failed_runs":2,"average_goal_score":0.4,"active_goals":["grow"],"learned_preferences":{"segment":"services"},"recurring_failures":["timeout"],"recurring_wins":["goal_reached"],"anti_patterns":["timeout"],"trends":{"goal_score_trend":"down"}}

def test_governance_advanced_route_handlers_expose_memory_extensions(monkeypatch) -> None:
    monkeypatch.setattr("interfaces.api.governance_advanced_route_handlers.GovernanceService.build_default", lambda: StubGovernance())
    handlers = GovernanceAdvancedRouteHandlers()
    assert handlers.promote_best_for_scenario(PromoteScenarioBaselineRequest(scenario="acquisition", run_ids=["run-1"])).baseline_name == "scenario/golden"
    assert handlers.rollback_timeline(RollbackTimelineRequest(baseline_name="b1")).timeline_text == "timeline:b1"
    assert handlers.drift_trend(DriftTrendRequest(baseline_name="b1", candidate_run_ids=["run-2"])).high_count == 1
    summary = handlers.business_memory_summary(BusinessMemoryGovernanceSummaryRequest(tenant_id="tenant-1", business_id="biz-1"))
    assert summary.anti_patterns == ["timeout"] and summary.trends["goal_score_trend"] == "down"
