from __future__ import annotations

"""Canonical human review surface with compat alias submodules."""

from dataclasses import dataclass
from typing import Any

class EscalationPolicy:
    def escalate(self, risk_level: str) -> bool:
        return risk_level in {"high", "critical"}

class OverrideAudit:
    def record(self, override_id: str, reviewer_id: str) -> dict[str, str]:
        return {"override_id": override_id, "reviewer_id": reviewer_id}

class OverrideExecution:
    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"executed": True, **payload}

class OverrideRegistry:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    def register(self, override_id: str, payload: dict[str, Any]) -> None:
        self._items[override_id] = dict(payload)

class ReviewAssignment:
    def assign(self, reviewer_ids: list[str]) -> str:
        if not reviewer_ids:
            raise ValueError("reviewer_ids must not be empty")
        return reviewer_ids[0]

@dataclass(frozen=True)
class ReviewDecision:
    reviewer_id: str
    approved: bool

@dataclass(frozen=True)
class ReviewRequest:
    request_id: str
    subject: str

class ReviewQueue:
    def __init__(self) -> None:
        self._items: list[ReviewRequest] = []

    def push(self, request: ReviewRequest) -> None:
        self._items.append(request)

    def pop(self) -> ReviewRequest:
        return self._items.pop(0)

GUIDELINES = (
    "verify evaluation",
    "verify safety",
    "verify reproducibility",
    "verify business objective alignment",
)

_ALIAS_EXPORTS = {
    "escalation_policy": "EscalationPolicy",
    "override_audit": "OverrideAudit",
    "override_execution": "OverrideExecution",
    "override_registry": "OverrideRegistry",
    "review_assignment": "ReviewAssignment",
    "review_decision": "ReviewDecision",
    "review_queue": "ReviewQueue",
    "review_request": "ReviewRequest",
    "reviewer_guidelines": "GUIDELINES",
}

__all__ = [
    "EscalationPolicy",
    "GUIDELINES",
    "OverrideAudit",
    "OverrideExecution",
    "OverrideRegistry",
    "ReviewAssignment",
    "ReviewDecision",
    "ReviewQueue",
    "ReviewRequest",
] + list(_ALIAS_EXPORTS)
