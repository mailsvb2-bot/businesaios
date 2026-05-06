from __future__ import annotations

from enum import Enum


class EconomicsSignalStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class BudgetPressureLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class MarginHealthStatus(str, Enum):
    STRONG = "strong"
    STABLE = "stable"
    WEAK = "weak"
    NEGATIVE = "negative"


class PaybackRiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"


class GuardSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    BLOCK = "block"


class BudgetPolicyMode(str, Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
