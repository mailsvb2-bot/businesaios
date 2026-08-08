from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .enums import RiskLevel, SalesHandoffReason


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


@dataclass(frozen=True, slots=True)
class SalesHandoffSignal:
    """Pure review signal; never an executable action or notification request."""

    tenant_id: str
    subject_id: str
    reason: SalesHandoffReason
    risk_level: RiskLevel
    summary: str
    context: Mapping[str, Any] = field(default_factory=dict)

    MAX_ID_CHARS = 240
    MAX_SUMMARY_CHARS = 500
    MAX_CONTEXT_BYTES = 32 * 1024

    def __post_init__(self) -> None:
        tenant = str(self.tenant_id or "").strip()
        subject = str(self.subject_id or "").strip()
        if not tenant or len(tenant) > self.MAX_ID_CHARS:
            raise ValueError("tenant_id must be 1..240 characters")
        if not subject or len(subject) > self.MAX_ID_CHARS:
            raise ValueError("subject_id must be 1..240 characters")
        reason = (
            self.reason
            if isinstance(self.reason, SalesHandoffReason)
            else SalesHandoffReason(str(self.reason).strip())
        )
        risk_level = (
            self.risk_level
            if isinstance(self.risk_level, RiskLevel)
            else RiskLevel(str(self.risk_level).strip())
        )
        summary = re.sub(r"\s+", " ", str(self.summary or "")).strip()
        if not summary or len(summary) > self.MAX_SUMMARY_CHARS:
            raise ValueError("summary must be 1..500 characters")
        context = dict(self.context or {})
        try:
            encoded = json.dumps(
                context,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("handoff context must be JSON serializable") from exc
        if len(encoded.encode("utf-8")) > self.MAX_CONTEXT_BYTES:
            raise ValueError("handoff context is too large")
        object.__setattr__(self, "tenant_id", tenant)
        object.__setattr__(self, "subject_id", subject)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "risk_level", risk_level)
        object.__setattr__(self, "summary", summary)
        object.__setattr__(self, "context", context)

    def as_feature(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "subject_id": self.subject_id,
            "operator_required": True,
            "reason": self.reason.value,
            "risk_level": self.risk_level.value,
            "summary": self.summary,
            "context": dict(self.context),
            "decision_authority": False,
            "effect_authority": False,
        }
