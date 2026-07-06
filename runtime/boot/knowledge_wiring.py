"""Runtime knowledge boot wiring through runtime.knowledge public API."""

from __future__ import annotations

from dataclasses import dataclass

from runtime.knowledge import (
    KnowledgeCommandService,
    KnowledgeExplainService,
    KnowledgeQueryService,
    KnowledgeService,
)

CANON_BOOT_WIRING_ONLY = True
CANON_RUNTIME_KNOWLEDGE_WIRING = True

@dataclass(frozen=True)
class RuntimeKnowledgeWiring:
    service: type[KnowledgeService] = KnowledgeService
    command_service: type[KnowledgeCommandService] = KnowledgeCommandService
    query_service: type[KnowledgeQueryService] = KnowledgeQueryService
    explain_service: type[KnowledgeExplainService] = KnowledgeExplainService


def build_runtime_knowledge_wiring() -> RuntimeKnowledgeWiring:
    return RuntimeKnowledgeWiring()


__all__ = [
    "CANON_BOOT_WIRING_ONLY",
    "CANON_RUNTIME_KNOWLEDGE_WIRING",
    "KnowledgeCommandService",
    "KnowledgeExplainService",
    "KnowledgeQueryService",
    "KnowledgeService",
    "RuntimeKnowledgeWiring",
    "build_runtime_knowledge_wiring",
]
