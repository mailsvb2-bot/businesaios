from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from contracts.event_store import EventStore

from ..serializers.knowledge_payload import deserialize_lesson, serialize_lesson
from ..types import Lesson, LessonQuery
from .event_store_codec import LESSON_EVENT_TYPE, append_knowledge_event, iter_knowledge_events


@dataclass(frozen=True)
class EventStoreLessonRepository:
    event_store: EventStore
    tenant_id: str

    def save(self, lesson: Lesson) -> Lesson:
        append_knowledge_event(
            self.event_store,
            tenant_id=self.tenant_id,
            event_type=LESSON_EVENT_TYPE,
            entity_id=lesson.lesson_id,
            payload=serialize_lesson(lesson),
        )
        return lesson

    def get(self, lesson_id: str) -> Lesson | None:
        items = {lesson.lesson_id: lesson for lesson in self.list_all()}
        return items.get(lesson_id)

    def list_all(self) -> Sequence[Lesson]:
        items: dict[str, Lesson] = {}
        for event in iter_knowledge_events(self.event_store, tenant_id=self.tenant_id, event_type=LESSON_EVENT_TYPE):
            payload = dict(event.get("payload") or {})
            lesson = deserialize_lesson(payload)
            items[lesson.lesson_id] = lesson
        return tuple(sorted(items.values(), key=lambda item: item.created_at, reverse=True))

    def find(self, query: LessonQuery) -> Sequence[Lesson]:
        items = list(self.list_all())
        if query.subject:
            subject = query.subject.strip().lower()
            items = [item for item in items if item.subject == subject]
        if query.tags:
            required = set(query.tags.values)
            items = [item for item in items if required.issubset(set(item.tags.values))]
        if query.free_text:
            text = query.free_text.strip().lower()
            items = [
                item for item in items
                if text in item.subject.lower() or text in item.title.lower() or text in item.narrative.lower()
            ]
        if query.created_after:
            items = [item for item in items if item.created_at >= query.created_after]
        if query.created_before:
            items = [item for item in items if item.created_at <= query.created_before]
        items.sort(key=lambda item: item.created_at, reverse=True)
        return tuple(items[: query.limit])
