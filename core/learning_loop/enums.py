from __future__ import annotations
from enum import Enum

class LearningRunStatus(str, Enum):
    PROPOSED = "proposed"
    BLOCKED = "blocked"
    RECORDED = "recorded"

class PromotionDecision(str, Enum):
    PROMOTE = "promote"
    HOLD = "hold"
    BLOCK = "block"
