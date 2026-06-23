from __future__ import annotations

"""Runtime boot knowledge bundle delegated through runtime.knowledge public API."""

from dataclasses import dataclass

from runtime.knowledge import (
    KnowledgeCommandService,
    KnowledgeExplainService,
    KnowledgeQueryService,
    KnowledgeService,
    Lesson,
    LessonDraft,
    MemoryRetrieval,
)

CANON_RUNTIME_BOOT_KNOWLEDGE_BUNDLE = True
CANON_BOOT_WIRING_ONLY = True


@dataclass(frozen=True)
class RuntimeKnowledgeBundle:
    service: type[KnowledgeService] = KnowledgeService
    command_service: type[KnowledgeCommandService] = KnowledgeCommandService
    query_service: type[KnowledgeQueryService] = KnowledgeQueryService
    explain_service: type[KnowledgeExplainService] = KnowledgeExplainService


def build_runtime_knowledge_bundle() -> RuntimeKnowledgeBundle:
    return RuntimeKnowledgeBundle()


__all__ = [
    "CANON_BOOT_WIRING_ONLY",
    "CANON_RUNTIME_BOOT_KNOWLEDGE_BUNDLE",
    "KnowledgeCommandService",
    "KnowledgeExplainService",
    "KnowledgeQueryService",
    "KnowledgeService",
    "Lesson",
    "LessonDraft",
    "MemoryRetrieval",
    "RuntimeKnowledgeBundle",
    "build_runtime_knowledge_bundle",
]
