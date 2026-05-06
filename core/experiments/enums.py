from __future__ import annotations

from enum import Enum


class ExperimentStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    EVALUATED = "evaluated"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class VariantRole(str, Enum):
    CONTROL = "control"
    TREATMENT = "treatment"


class MetricDirection(str, Enum):
    INCREASE = "increase"
    DECREASE = "decrease"


class RolloutDecision(str, Enum):
    HOLD = "hold"
    PARTIAL = "partial"
    FULL = "full"
    BLOCK = "block"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
