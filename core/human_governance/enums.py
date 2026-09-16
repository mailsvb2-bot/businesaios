from __future__ import annotations

from enum import Enum

from contracts.risk import RiskLevel as RiskLevel


class ReviewStatus(str, Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAUSED = "paused"
    ESCALATED = "escalated"
    CLOSED = "closed"


class EscalationLevel(str, Enum):
    TEAM_LEAD = "team_lead"
    GOVERNANCE = "governance"
    EXECUTIVE = "executive"
