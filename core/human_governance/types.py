from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any, Mapping


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True)
class ReviewItem:
    review_id: str
    decision_id: str
    subject_type: str
    subject_id: str
    reason: str
    risk_level: str
    status: str
    requested_by: str
    requested_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=dict)
    updated_at: datetime | None = None


@dataclass(frozen=True)
class ApprovalState:
    review_id: str
    status: str
    decided_by: str | None
    decided_at: datetime | None
    reason: str | None = None


@dataclass(frozen=True)
class ApprovalDecision:
    review_id: str
    actor_id: str
    rationale: str
    decided_at: datetime


@dataclass(frozen=True)
class ReviewCase:
    review: ReviewItem
    state: ApprovalState | None
    need_approval: bool
    escalation_risk: float
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class OverrideRecord:
    override_id: str
    review_id: str
    actor_id: str
    reason: str
    created_at: datetime
    scope: str = "review"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EscalationRecord:
    escalation_id: str
    review_id: str
    level: str
    created_at: datetime
    reason: str
    is_open: bool = True
