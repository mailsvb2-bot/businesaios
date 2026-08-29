from __future__ import annotations

import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

EventRecord = dict[str, Any]
BUSINESS_FACT_EVENT_TYPE = "business_fact.v1"

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

@dataclass(frozen=True)
class BusinessFactV1:
    fact_id: str
    tenant_id: str
    business_id: str
    fact_type: str
    entity_id: str
    event_time_ms: int
    observed_at_ms: int
    source: str
    payload: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None
    supersedes_fact_id: str | None = None
    decision_id: str | None = None
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        if not all(str(getattr(self, name) or "").strip() for name in ("fact_id", "tenant_id", "business_id", "fact_type", "entity_id", "source")):
            raise ValueError("BusinessFactV1 identity and source fields are required")

    def as_event(self) -> EventRecord:
        payload = {"schema_version": 1, "business_id": self.business_id, "fact_type": self.fact_type, "entity_id": self.entity_id, "event_time_ms": int(self.event_time_ms), "observed_at_ms": int(self.observed_at_ms), "payload": dict(self.payload or {}), "provenance": dict(self.provenance or {}), "supersedes_fact_id": self.supersedes_fact_id}
        return {"event_id": self.fact_id, "tenant_id": self.tenant_id, "source": self.source, "event_type": BUSINESS_FACT_EVENT_TYPE, "timestamp_ms": int(self.observed_at_ms), "decision_id": self.decision_id, "correlation_id": self.correlation_id, "payload": payload}

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
        excluded = {"event_id", "tenant_id", "user_id", "source", "event_type", "type", "timestamp_ms", "decision_id", "correlation_id", "payload"}
        payload_obj = {k: v for k, v in e.items() if k not in excluded}
    if not isinstance(payload_obj, dict):
        payload_obj = {"value": payload_obj}
    return AppendEvent(
        event_id=event_id,
        tenant_id=tenant_id,
        user_id=e.get("user_id"),
        source=source,
        event_type=event_type,
        timestamp_ms=int(e.get("timestamp_ms") or int(time.time() * 1000)),
        decision_id=e.get("decision_id") or e.get("decision") or e.get("decision_ref"),
        correlation_id=e.get("correlation_id") or e.get("correlation") or e.get("trace_id"),
        payload=dict(payload_obj),
    )

@runtime_checkable
class EventStoreReader(Protocol):
    def iter_events(self, *, tenant_id: str, start_ms: int, end_ms: int | None = None, user_id: str | None = None, event_type: str | None = None) -> Iterable[EventRecord]: ...
    def count_events(self, *, tenant_id: str, start_ms: int, end_ms: int, user_id: str | None = None, event_type: str | None = None) -> int: ...

@runtime_checkable
class EventStoreWriter(Protocol):
    def append_event(self, event: EventRecord) -> None: ...

@runtime_checkable
class EventStore(EventStoreReader, EventStoreWriter, Protocol):
    pass

def supports_event_store(obj: Any) -> bool:
    return bool(obj is not None and hasattr(obj, "append_event") and hasattr(obj, "iter_events") and hasattr(obj, "count_events"))

def iter_events_strict(store: EventStoreReader, *, tenant_id: str, start_ms: int, end_ms: int | None = None, user_id: str | None = None, event_type: str | None = None) -> Iterable[EventRecord]:
    return store.iter_events(tenant_id=str(tenant_id), start_ms=int(start_ms), end_ms=(int(end_ms) if end_ms is not None else None), user_id=(str(user_id) if user_id is not None else None), event_type=(str(event_type) if event_type is not None else None))
