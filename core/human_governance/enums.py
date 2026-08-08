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


class SalesHandoffReason(str, Enum):
    EXPLICIT_REQUEST = "explicit_request"
    LOW_CONFIDENCE = "low_confidence"
    SENSITIVE_CONTEXT = "sensitive_context"
    PRICING_EXCEPTION = "pricing_exception"
    NEGATIVE_SENTIMENT = "negative_sentiment"
    REPEATED_FAILURE = "repeated_failure"
