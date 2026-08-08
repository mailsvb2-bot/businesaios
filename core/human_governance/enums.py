from __future__ import annotations

from enum import Enum


class ReviewStatus(str, Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAUSED = "paused"
    ESCALATED = "escalated"
    CLOSED = "closed"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EscalationLevel(str, Enum):
    TEAM_LEAD = "team_lead"
    GOVERNANCE = "governance"
    EXECUTIVE = "executive"
