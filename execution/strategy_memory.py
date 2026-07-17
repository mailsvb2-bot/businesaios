from __future__ import annotations

from application.planning.strategy_memory import (
    CANON_STRATEGY_MEMORY as CANON_STRATEGY_MEMORY,
    FileStrategyMemoryStore as FileStrategyMemoryStore,
    STRATEGY_MEMORY_SCHEMA_VERSION as STRATEGY_MEMORY_SCHEMA_VERSION,
    StrategyMemoryService as StrategyMemoryService,
    StrategyMemorySnapshot as StrategyMemorySnapshot,
    StrategyPatternStat as StrategyPatternStat,
)

CANON_STRATEGY_MEMORY_COMPAT_SHIM = True
CANON_STRATEGY_MEMORY_FINAL_OWNER = "application.planning.strategy_memory"
CANON_STRATEGY_MEMORY_SURFACE = "StrategyMemoryService"

__all__ = [
    "CANON_STRATEGY_MEMORY",
    "CANON_STRATEGY_MEMORY_COMPAT_SHIM",
    "CANON_STRATEGY_MEMORY_FINAL_OWNER",
    "CANON_STRATEGY_MEMORY_SURFACE",
    "FileStrategyMemoryStore",
    "STRATEGY_MEMORY_SCHEMA_VERSION",
    "StrategyMemoryService",
    "StrategyMemorySnapshot",
    "StrategyPatternStat",
]
