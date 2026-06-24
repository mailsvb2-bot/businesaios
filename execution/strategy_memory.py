from __future__ import annotations

from application.planning.strategy_memory import (
    CANON_STRATEGY_MEMORY,
    FileStrategyMemoryStore,
    STRATEGY_MEMORY_SCHEMA_VERSION,
    StrategyMemoryService,
    StrategyMemorySnapshot,
    StrategyPatternStat,
)

CANON_STRATEGY_MEMORY_COMPAT_SHIM = True
CANON_STRATEGY_MEMORY_FINAL_OWNER = "application.planning.strategy_memory"
