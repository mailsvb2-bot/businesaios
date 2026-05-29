from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.knowledge.enums import SourceKind
from core.knowledge.types import LessonDraft, MemoryRetrieval, TagSet
from runtime.boot.knowledge_boot import build_knowledge_services
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def test_knowledge_bundle_records_and_retrieves() -> None:
    bundle = build_knowledge_services(event_store=MemoryEventStore(), tenant_id="tenant-a")
    lesson = bundle.command_service.record_lesson(
        LessonDraft(
            subject="pricing",
            title="Keep moderate discounting",
            narrative="Moderate discounting preserved margin.",
            source_kind=SourceKind.EXPERIMENT,
            source_ref="exp-7",
            tags=TagSet.from_iterable(["pricing", "discount"]),
            observed_at=datetime.now(tz=UTC) - timedelta(days=2),
            created_by="tester",
            evidence_refs=("e1",),
        )
    )
    summary = bundle.query_service.retrieve_memory(
        MemoryRetrieval(
            target_subject="pricing",
            task="discount policy",
            tags=TagSet.from_iterable(["pricing"]),
            now=datetime.now(tz=UTC),
            strict_mode=True,
        )
    )
    assert lesson.lesson_id
    assert summary.entries
