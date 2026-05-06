from __future__ import annotations

from runtime.knowledge import MemoryRetrieval
from runtime.boot.knowledge_bundle import KnowledgeRuntimeBundle

CANON_THIN_HANDLER = True


def handle_knowledge_explain(*, bundle: KnowledgeRuntimeBundle, retrieval: MemoryRetrieval) -> str:
    return bundle.explain_service.explain_retrieval(retrieval)
