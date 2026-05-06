from __future__ import annotations
CANON_BOOT_WIRING_ONLY = True
CANON_BOOT_KNOWLEDGE_BUNDLE_FINAL_OWNER = True


from dataclasses import dataclass

from runtime.knowledge import (
    KnowledgeCommandService,
    KnowledgeExplainService,
    KnowledgeQueryService,
    LessonDeduplicator,
    LessonDraftIngestionAdapter,
)


@dataclass(frozen=True)
class KnowledgeRuntimeBundle:
    command_service: KnowledgeCommandService
    query_service: KnowledgeQueryService
    explain_service: KnowledgeExplainService
    ingestion_adapter: LessonDraftIngestionAdapter
    deduplicator: LessonDeduplicator
