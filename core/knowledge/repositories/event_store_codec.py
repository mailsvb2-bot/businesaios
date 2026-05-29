from __future__ import annotations

from datetime import datetime, timezone, UTC
from typing import Any, Iterable, Mapping

from contracts.event_store import EventRecord, EventStoreReader, EventStoreWriter, iter_events_strict

KNOWLEDGE_STREAM_USER_ID = "knowledge"
LESSON_EVENT_TYPE = "knowledge.lesson.saved.v1"
PATTERN_EVENT_TYPE = "knowledge.pattern.saved.v1"
MEMORY_LINK_EVENT_TYPE = "knowledge.memory_link.saved.v1"


def utc_now_ms() -> int:
    return int(datetime.now(tz=UTC).timestamp() * 1000)


def append_knowledge_event(
    store: EventStoreWriter,
    *,
    tenant_id: str,
    event_type: str,
    entity_id: str,
    payload: Mapping[str, Any],
) -> None:
    store.append_event(
        {
            "tenant_id": str(tenant_id),
            "user_id": KNOWLEDGE_STREAM_USER_ID,
            "event_type": event_type,
            "timestamp_ms": utc_now_ms(),
            "entity_id": str(entity_id),
            "payload": dict(payload),
        }
    )


def iter_knowledge_events(
    store: EventStoreReader,
    *,
    tenant_id: str,
    event_type: str,
) -> Iterable[EventRecord]:
    return iter_events_strict(store, tenant_id=str(tenant_id), start_ms=0, end_ms=None, user_id=KNOWLEDGE_STREAM_USER_ID, event_type=event_type)
