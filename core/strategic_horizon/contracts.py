from __future__ import annotations

from enum import Enum

CANON_STRATEGIC_HORIZON_CONTRACTS = True


class StrategicMode(str, Enum):
    STABILIZE = "stabilize"
    OPTIMIZE = "optimize"
    EXPAND = "expand"
    RESEARCH = "research"
    DEFENSE = "defense"


class LearningRegime(str, Enum):
    FROZEN = "frozen"
    SAFE = "safe"
    AGGRESSIVE = "aggressive"


__all__ = ["CANON_STRATEGIC_HORIZON_CONTRACTS", "LearningRegime", "StrategicMode"]
