from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

from contracts.event_store import EventStore

from ..serializers.knowledge_payload import deserialize_memory_link, serialize_memory_link
from ..types import MemoryLink
from .event_store_codec import MEMORY_LINK_EVENT_TYPE, append_knowledge_event, iter_knowledge_events


@dataclass(frozen=True)
class EventStoreMemoryLinkRepository:
    event_store: EventStore
    tenant_id: str

    def save(self, link: MemoryLink) -> MemoryLink:
        append_knowledge_event(
            self.event_store,
            tenant_id=self.tenant_id,
            event_type=MEMORY_LINK_EVENT_TYPE,
            entity_id=link.link_id,
            payload=serialize_memory_link(link),
        )
        return link

    def list_for_target(self, target_id: str) -> Sequence[MemoryLink]:
        return tuple(link for link in self.list_all() if link.target_id == target_id)

    def list_for_source(self, source_id: str) -> Sequence[MemoryLink]:
        return tuple(link for link in self.list_all() if link.source_id == source_id)

    def list_all(self) -> Sequence[MemoryLink]:
        items: dict[str, MemoryLink] = {}
        for event in iter_knowledge_events(self.event_store, tenant_id=self.tenant_id, event_type=MEMORY_LINK_EVENT_TYPE):
            payload = dict(event.get("payload") or {})
            link = deserialize_memory_link(payload)
            items[link.link_id] = link
        return tuple(sorted(items.values(), key=lambda item: item.created_at, reverse=True))
