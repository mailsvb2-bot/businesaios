from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .contracts import KnowledgeGuard as KnowledgeGuardContract
from .guards.stale_memory_guard import StaleMemoryGuard
from .guards.unsafe_reuse_guard import UnsafeReuseGuard
from .guards.weak_pattern_guard import WeakPatternGuard
from .types import MemoryRetrieval, StrategyMemoryEntry


@dataclass(frozen=True)
class KnowledgeGuard(KnowledgeGuardContract):
    stale_memory_guard: StaleMemoryGuard
    weak_pattern_guard: WeakPatternGuard
    unsafe_reuse_guard: UnsafeReuseGuard

    def ensure_reuse_is_safe(self, retrieval: MemoryRetrieval, entries: Sequence[StrategyMemoryEntry]) -> None:
        self.stale_memory_guard.ensure_entries_are_fresh(retrieval, entries)
        self.weak_pattern_guard.ensure_entries_are_strong(entries)
        self.unsafe_reuse_guard.ensure_reuse_is_safe(retrieval, entries)
