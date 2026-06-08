from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Protocol


class EventAppendProtocol(Protocol):
    def append(self, event: dict[str, Any]) -> object: ...

@dataclass(frozen=True)
class AppendEvent:
    event_id: str
    tenant_id: str
    user_id: Any
    source: str
    event_type: str
    timestamp_ms: int
    decision_id: Any
    correlation_id: Any
    payload: dict[str, Any]


def normalize_append_event(event: dict | None) -> AppendEvent:
    e = dict(event or {})
    event_id = str(e.get("event_id") or uuid.uuid4())
    tenant_id = str(e.get("tenant_id") or "").strip()
    if not tenant_id:
        raise ValueError("tenant_id is required (strict)")
    event_type = str(e.get("event_type") or e.get("type") or "").strip()
    if not event_type:
        raise ValueError("MISSING_EVENT_TYPE")
    source = str(e.get("source") or "system").strip() or "system"
    payload_obj = e.get("payload")
    if payload_obj is None:
        payload_obj = {
            k: v
            for k, v in e.items()
            if k
            not in {
                "event_id",
                "tenant_id",
                "user_id",
                "source",
                "event_type",
                "type",
                "timestamp_ms",
                "decision_id",
                "correlation_id",
                "payload",
            }
        }
    if not isinstance(payload_obj, dict):
        payload_obj = {"value": payload_obj}
    decision_id = e.get("decision_id") or e.get("decision") or e.get("decision_ref")
    correlation_id = e.get("correlation_id") or e.get("correlation") or e.get("trace_id")
    return AppendEvent(
        event_id=event_id,
        tenant_id=tenant_id,
        user_id=e.get("user_id"),
        source=source,
        event_type=event_type,
        timestamp_ms=int(e.get("timestamp_ms") or int(time.time() * 1000)),
        decision_id=decision_id,
        correlation_id=correlation_id,
        payload=dict(payload_obj),
    )


__all__ = ["AppendEvent", "EventAppendProtocol", "normalize_append_event"]
