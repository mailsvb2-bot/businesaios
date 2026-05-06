from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


CANON_HEADLESS_TRACE = True


@dataclass(frozen=True)
class HeadlessTraceEvent:
    trace_id: str
    run_id: str
    event_type: str
    ts_ms: int
    step_index: int
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class HeadlessTrace:
    trace_id: str
    run_id: str
    business_id: str
    tenant_id: str
    goal: str
    events: list[HeadlessTraceEvent] = field(default_factory=list)

    @classmethod
    def start(cls, *, goal: str, business_id: str, tenant_id: str) -> "HeadlessTrace":
        run_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        trace = cls(
            trace_id=trace_id,
            run_id=run_id,
            business_id=business_id,
            tenant_id=tenant_id,
            goal=goal,
        )
        trace.record(
            event_type="trace_started",
            step_index=0,
            payload={
                "goal": str(goal),
                "business_id": str(business_id),
                "tenant_id": str(tenant_id),
            },
        )
        return trace

    def record(self, *, event_type: str, step_index: int, payload: dict[str, Any] | None = None) -> None:
        self.events.append(
            HeadlessTraceEvent(
                trace_id=self.trace_id,
                run_id=self.run_id,
                event_type=str(event_type),
                ts_ms=int(time.time() * 1000),
                step_index=int(step_index),
                payload=dict(payload or {}),
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "run_id": self.run_id,
            "business_id": self.business_id,
            "tenant_id": self.tenant_id,
            "goal": self.goal,
            "events": [
                {
                    "trace_id": e.trace_id,
                    "run_id": e.run_id,
                    "event_type": e.event_type,
                    "ts_ms": e.ts_ms,
                    "step_index": e.step_index,
                    "payload": dict(e.payload),
                }
                for e in self.events
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)


__all__ = [
    "CANON_HEADLESS_TRACE",
    "HeadlessTrace",
    "HeadlessTraceEvent",
]
