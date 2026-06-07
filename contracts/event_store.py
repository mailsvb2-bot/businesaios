from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from collections.abc import Iterable

EventRecord = dict[str, Any]

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
