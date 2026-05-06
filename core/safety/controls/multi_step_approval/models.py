from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ApprovalWorkflowState(str, Enum):
    REQUESTED = 'requested'
    PENDING = 'pending'
    PARTIALLY_APPROVED = 'partially_approved'
    APPROVED = 'approved'
    EXECUTED = 'executed'
    REJECTED = 'rejected'
    EXPIRED = 'expired'
    CANCELLED = 'cancelled'
    SUPERSEDED = 'superseded'


@dataclass(frozen=True)
class ApprovalPolicy:
    min_approvals: int = 2
    action_prefixes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApprovalTicket:
    action_id: str
    approvals: tuple[str, ...] = field(default_factory=tuple)
    state: ApprovalWorkflowState = ApprovalWorkflowState.PENDING
    rejections: tuple[str, ...] = field(default_factory=tuple)
    requested_by: str = ''
    expires_at: str = ''
    required_approvals: int = 0
    escalation_level: int = 0
    version: int = 0
    lease_owner: str = ''
    fencing_token: int = 0

    @property
    def approved(self) -> bool:
        return self.state in {ApprovalWorkflowState.APPROVED, ApprovalWorkflowState.EXECUTED}
