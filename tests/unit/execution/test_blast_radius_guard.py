from __future__ import annotations

from application.headless.models import GoalExecutionRequest
from execution.blast_radius_guard import BlastRadiusGuard


class EventLogStub:
    def __init__(self, count: int) -> None:
        self.count = count

    def query_recent(self, *, event_type, since_ms, filters):
        return [object()] * int(self.count)


def test_blast_radius_guard_blocks_when_hourly_limit_is_exceeded() -> None:
    guard = BlastRadiusGuard()
    request = GoalExecutionRequest(goal="grow", business_id="b1", constraints={"blast_radius_max_per_hour": 1})
    decision = guard.evaluate(request=request, action_type="send_message@v1", event_log=EventLogStub(1))
    assert decision.allowed is False
    assert decision.reason == "blast_radius_exceeded"


def test_blast_radius_guard_enforces_phase7_new_leads_per_hour_budget() -> None:
    guard = BlastRadiusGuard()
    request = GoalExecutionRequest(
        goal="grow",
        business_id="b1",
        autonomy_tier="bounded_autonomy",
    )
    decision = guard.evaluate(
        request=request,
        action_type="send_message@v1",
        payload={
            "lead_count": 1,
            "persistent_counters": {"leads_hour": 10},
        },
    )
    assert decision.allowed is False
    assert "autonomy_max_new_leads_per_hour" in decision.details["violated_limits"]


def test_blast_radius_guard_enforces_phase7_campaigns_per_day_budget() -> None:
    guard = BlastRadiusGuard()
    request = GoalExecutionRequest(
        goal="grow",
        business_id="b1",
        autonomy_tier="bounded_autonomy",
    )
    decision = guard.evaluate(
        request=request,
        action_type="launch_campaign",
        payload={
            "campaign_count": 1,
            "persistent_counters": {"campaigns_day": 3},
        },
    )
    assert decision.allowed is False
    assert "autonomy_max_campaigns_per_day" in decision.details["violated_limits"]
