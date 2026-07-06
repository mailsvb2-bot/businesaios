from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from contracts.event_store import EventStore

from ..serializers.knowledge_payload import deserialize_pattern, serialize_pattern
from ..types import Pattern
from .event_store_codec import PATTERN_EVENT_TYPE, append_knowledge_event, iter_knowledge_events


@dataclass(frozen=True)
class EventStorePatternRepository:
    event_store: EventStore
    tenant_id: str

    def save(self, pattern: Pattern) -> Pattern:
        append_knowledge_event(
            self.event_store,
            tenant_id=self.tenant_id,
            event_type=PATTERN_EVENT_TYPE,
            entity_id=pattern.pattern_id,
            payload=serialize_pattern(pattern),
        )
        return pattern

    def get(self, pattern_id: str) -> Pattern | None:
        items = {pattern.pattern_id: pattern for pattern in self.list_all()}
        return items.get(pattern_id)

    def list_all(self) -> Sequence[Pattern]:
        items: dict[str, Pattern] = {}
        for event in iter_knowledge_events(self.event_store, tenant_id=self.tenant_id, event_type=PATTERN_EVENT_TYPE):
            payload = dict(event.get("payload") or {})
            pattern = deserialize_pattern(payload)
            items[pattern.pattern_id] = pattern
        return tuple(sorted(items.values(), key=lambda item: (item.confidence_score, item.created_at), reverse=True))

    def find_by_subject(self, subject: str) -> Sequence[Pattern]:
        normalized = subject.strip().lower()
        items = [item for item in self.list_all() if item.subject == normalized]
        items.sort(key=lambda item: (item.confidence_score, item.created_at), reverse=True)
        return tuple(items)
