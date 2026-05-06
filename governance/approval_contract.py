from __future__ import annotations

"""
Approval contract.

Approval remains subordinate to canonical execution:
DecisionCore decides the action.
Governance checks whether execution is authorized.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping, Protocol

from core.tenancy.normalization import require_tenant_id
from governance.rbac_contract import RoleId


CANON_GOVERNANCE_APPROVAL_CONTRACT = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalStatus(str, Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ApprovalOutcome(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


@dataclass(frozen=True)
class ApprovalRequest:
    approval_id: str
    tenant_id: str
    subject_type: str
    subject_id: str
    requested_by: str
    reason: str
    required_role_groups: tuple[tuple[RoleId, ...], ...] = ()
    min_distinct_approvers: int = 1
    prohibit_self_approval: bool = True
    created_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.approval_id or "").strip():
            raise ValueError("approval_id is required")
        require_tenant_id(self.tenant_id)
        if not str(self.subject_type or "").strip():
            raise ValueError("subject_type is required")
        if not str(self.subject_id or "").strip():
            raise ValueError("subject_id is required")
        if not str(self.requested_by or "").strip():
            raise ValueError("requested_by is required")
        if not str(self.reason or "").strip():
            raise ValueError("reason is required")
        if int(self.min_distinct_approvers) < 1:
            raise ValueError("min_distinct_approvers must be >= 1")
        for group in self.required_role_groups:
            if not group:
                raise ValueError("required_role_groups must not contain empty groups")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("expires_at must be greater than created_at")


@dataclass(frozen=True)
class ApprovalDecision:
    approval_id: str
    tenant_id: str
    actor_id: str
    role_id: RoleId
    outcome: ApprovalOutcome
    rationale: str
    decided_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.approval_id or "").strip():
            raise ValueError("approval_id is required")
        require_tenant_id(self.tenant_id)
        if not str(self.actor_id or "").strip():
            raise ValueError("actor_id is required")
        if not str(self.rationale or "").strip():
            raise ValueError("rationale is required")


@dataclass(frozen=True)
class ApprovalRecord:
    request: ApprovalRequest
    status: ApprovalStatus
    decisions: tuple[ApprovalDecision, ...] = ()
    final_reason: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            ApprovalStatus.APPROVED,
            ApprovalStatus.REJECTED,
            ApprovalStatus.CANCELLED,
            ApprovalStatus.EXPIRED,
        }


class ApprovalStoreContract(Protocol):
    def create(self, request: ApprovalRequest) -> ApprovalRecord: ...
    def get(self, approval_id: str) -> ApprovalRecord | None: ...
    def save(self, record: ApprovalRecord) -> ApprovalRecord: ...
    def list_open(self, *, tenant_id: str) -> tuple[ApprovalRecord, ...]: ...


__all__ = [
    "ApprovalDecision",
    "ApprovalOutcome",
    "ApprovalRecord",
    "ApprovalRequest",
    "ApprovalStatus",
    "ApprovalStoreContract",
    "CANON_GOVERNANCE_APPROVAL_CONTRACT",
    "utc_now",
]
