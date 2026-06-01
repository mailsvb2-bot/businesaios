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
