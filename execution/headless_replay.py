from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.headless.models import GoalExecutionReport, GoalExecutionRequest


CANON_HEADLESS_REPLAY = True


@dataclass(frozen=True)
class HeadlessReplayEngine:
    """
    Replays a prior headless run by reconstructing the original request shape
    from the persisted ledger record and re-running the same execution contract.
    """

    contract: Any

    def replay(self, record: dict[str, Any]) -> GoalExecutionReport:
        trace = dict(record.get("trace") or {})
        events = list(trace.get("events") or [])
        started = None
        for event in events:
            if event.get("event_type") == "request_received":
                started = dict(event.get("payload") or {})
                break
        if not started:
            raise ValueError("cannot replay: request_received event not found")

        request = GoalExecutionRequest(
            goal=str(started["goal"]),
            business_id=str(started["business_id"]),
            tenant_id=str(started["tenant_id"]),
            user_id=started.get("user_id"),
            region=str(started.get("region") or "global"),
            max_steps=int(started.get("max_steps") or 1),
            profile=dict(started.get("profile") or {}),
            signals=list(started.get("signals") or []),
            constraints=dict(started.get("constraints") or {}),
            economy=dict(started.get("economy") or {}),
            meta=dict(started.get("meta") or {}),
        )
        return self.contract.execute_autopilot(request)


__all__ = [
    "CANON_HEADLESS_REPLAY",
    "HeadlessReplayEngine",
]
