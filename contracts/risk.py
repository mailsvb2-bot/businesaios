from __future__ import annotations

from enum import Enum

CANON_RISK_SEVERITY_CONTRACT = True


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


__all__ = ["CANON_RISK_SEVERITY_CONTRACT", "RiskLevel"]
