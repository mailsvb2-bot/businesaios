from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.knowledge.builders.lesson_builder import LessonBuilder
from core.knowledge.builders.pattern_builder import PatternBuilder
from core.knowledge.enums import KnowledgeKind, SourceKind
from core.knowledge.repositories.lesson_repository import EventStoreLessonRepository
from core.knowledge.repositories.memory_link_repository import EventStoreMemoryLinkRepository
from core.knowledge.repositories.pattern_repository import EventStorePatternRepository
from core.knowledge.types import LessonDraft, MemoryLink, PatternDraft, TagSet
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def test_event_store_repositories_roundtrip() -> None:
    store = MemoryEventStore()
    tenant_id = "tenant-a"
    lesson_repo = EventStoreLessonRepository(event_store=store, tenant_id=tenant_id)
    pattern_repo = EventStorePatternRepository(event_store=store, tenant_id=tenant_id)
    link_repo = EventStoreMemoryLinkRepository(event_store=store, tenant_id=tenant_id)

    lesson = LessonBuilder().build(
        LessonDraft(
            subject="pricing",
            title="Win-back discount degraded margin",
            narrative="Discounting improved conversions but hurt margin.",
            source_kind=SourceKind.EXPERIMENT,
            source_ref="exp-1",
            tags=TagSet.from_iterable(["pricing", "margin"]),
            observed_at=datetime.now(tz=timezone.utc) - timedelta(days=1),
            created_by="tester",
            evidence_refs=("e1",),
        )
    )
    lesson_repo.save(lesson)

    pattern = PatternBuilder().build(
        PatternDraft(
            subject="pricing",
            hypothesis="deep discounts reduce margin quality",
            lesson_ids=(lesson.lesson_id,),
            signal_count=3,
            contradictory_signal_count=1,
            tags=TagSet.from_iterable(["pricing"]),
            created_by="tester",
        )
    )
    pattern_repo.save(pattern)

    link = MemoryLink(
        link_id="",
        source_kind=KnowledgeKind.LESSON,
        source_id=lesson.lesson_id,
        target_kind=KnowledgeKind.PATTERN,
        target_id=pattern.pattern_id,
        rationale="lesson supports pattern",
        created_at=datetime.now(tz=timezone.utc),
        created_by="tester",
    )
    saved_link = link_repo.save(link)

    assert lesson_repo.get(lesson.lesson_id) is not None
    assert pattern_repo.get(pattern.pattern_id) is not None
    assert link_repo.list_for_target(pattern.pattern_id)[0].source_id == lesson.lesson_id
    assert saved_link.link_id == ""
