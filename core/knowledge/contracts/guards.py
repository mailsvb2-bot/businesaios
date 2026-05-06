"""Guard protocols for knowledge domain."""
from __future__ import annotations

from typing import Protocol, Sequence

from ..types import MemoryRetrieval, StrategyMemoryEntry

__all__ = ["KnowledgeGuard"]


class KnowledgeGuard(Protocol):
    def ensure_reuse_is_safe(
        self,
        retrieval: MemoryRetrieval,
        entries: Sequence[StrategyMemoryEntry],
    ) -> None: ...
