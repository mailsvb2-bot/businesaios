from __future__ import annotations

from runtime.knowledge import Lesson, LessonDraft
from runtime.boot.knowledge_bundle import KnowledgeRuntimeBundle

CANON_THIN_HANDLER = True


def handle_knowledge_build(*, bundle: KnowledgeRuntimeBundle, draft: LessonDraft) -> Lesson:
    return bundle.command_service.record_lesson(draft)
