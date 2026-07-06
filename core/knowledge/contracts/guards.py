"""Guard protocols for knowledge domain."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from ..types import MemoryRetrieval, StrategyMemoryEntry

__all__ = ["KnowledgeGuard"]


class KnowledgeGuard(Protocol):
    def ensure_reuse_is_safe(
        self,
        retrieval: MemoryRetrieval,
        entries: Sequence[StrategyMemoryEntry],
    ) -> None: ...
