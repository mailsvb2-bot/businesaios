from __future__ import annotations

from enum import Enum


class SourceKind(str, Enum):
    EXPERIMENT = "experiment"
    INCIDENT = "incident"
    CAMPAIGN = "campaign"
    CUSTOMER = "customer"
    SALES = "sales"
    OPERATOR = "operator"
    AI_ANALYSIS = "ai_analysis"
    MANUAL = "manual"


class KnowledgeKind(str, Enum):
    LESSON = "lesson"
    PATTERN = "pattern"
    MEMORY_LINK = "memory_link"


class LessonStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    SUPERSEDED = "superseded"


class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OutcomePolarity(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ReuseSafety(str, Enum):
    SAFE = "safe"
    CAUTION = "caution"
    BLOCKED = "blocked"
