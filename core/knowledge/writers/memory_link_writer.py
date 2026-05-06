from __future__ import annotations

from dataclasses import dataclass

from ..contracts import MemoryLinkRepository, MemoryLinkWriter as MemoryLinkWriterContract
from ..errors import KnowledgeValidationError
from ..ids import new_memory_link_id
from ..types import MemoryLink


@dataclass(frozen=True)
class MemoryLinkWriter(MemoryLinkWriterContract):
    repository: MemoryLinkRepository

    def write(self, link: MemoryLink) -> MemoryLink:
        normalized = self._normalize(link)
        return self.repository.save(normalized)

    @staticmethod
    def _normalize(link: MemoryLink) -> MemoryLink:
        source_id = link.source_id.strip()
        target_id = link.target_id.strip()
        rationale = link.rationale.strip()
        created_by = link.created_by.strip()
        if not source_id:
            raise KnowledgeValidationError("MemoryLink source_id is required.")
        if not target_id:
            raise KnowledgeValidationError("MemoryLink target_id is required.")
        if not rationale:
            raise KnowledgeValidationError("MemoryLink rationale is required.")
        if not created_by:
            raise KnowledgeValidationError("MemoryLink created_by is required.")
        if link.created_at.tzinfo is None:
            raise KnowledgeValidationError("MemoryLink created_at must be timezone-aware.")
        if source_id == target_id and link.source_kind == link.target_kind:
            raise KnowledgeValidationError("MemoryLink cannot self-link the same entity.")
        link_id = link.link_id.strip() or new_memory_link_id()
        return MemoryLink(
            link_id=link_id,
            source_kind=link.source_kind,
            source_id=source_id,
            target_kind=link.target_kind,
            target_id=target_id,
            rationale=rationale,
            created_at=link.created_at,
            created_by=created_by,
        )
