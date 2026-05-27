from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Protocol

from runtime.platform.safety_approval_repository import (
    CANON_PLATFORM_SAFETY_APPROVAL_REPOSITORY,
    SCHEMA_VERSION,
    PlatformSqliteApprovalRepository,
)

from .models import ApprovalTicket, ApprovalWorkflowState

CANON_SAFETY_APPROVAL_REPOSITORY = True


class ApprovalRepository(Protocol):
    def get(self, action_id: str) -> ApprovalTicket: ...
    def put(self, ticket: ApprovalTicket) -> None: ...
    def record_approval(self, *, action_id: str, approver: str) -> ApprovalTicket: ...
    def record_rejection(self, *, action_id: str, approver: str) -> ApprovalTicket: ...
    def mark_executed(self, *, action_id: str) -> ApprovalTicket: ...


@dataclass
class InMemoryApprovalRepository:
    tickets: dict[str, ApprovalTicket] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def get(self, action_id: str) -> ApprovalTicket:
        with self._lock:
            return self.tickets.get(str(action_id), ApprovalTicket(action_id=str(action_id)))

    def put(self, ticket: ApprovalTicket) -> None:
        with self._lock:
            current = self.tickets.get(str(ticket.action_id))
            version = int(ticket.version if ticket.version else ((current.version + 1) if current else 1))
            self.tickets[str(ticket.action_id)] = ApprovalTicket(**{**ticket.__dict__, 'version': version})

    def acquire_lease(self, *, action_id: str, owner: str) -> ApprovalTicket:
        with self._lock:
            current = self.get(action_id)
            leased = ApprovalTicket(**{**current.__dict__, 'lease_owner': str(owner), 'version': int(current.version) + 1, 'fencing_token': int(current.fencing_token) + 1})
            self.tickets[str(action_id)] = leased
            return leased

    def compare_and_set(self, *, expected_version: int, ticket: ApprovalTicket) -> ApprovalTicket:
        with self._lock:
            current = self.get(ticket.action_id)
            if int(current.version) != int(expected_version):
                raise RuntimeError('approval_ticket_version_conflict')
            if current.lease_owner and ticket.lease_owner and current.lease_owner != ticket.lease_owner and int(ticket.fencing_token or 0) < int(current.fencing_token or 0):
                raise RuntimeError('approval_ticket_stale_fencing_token')
            updated = ApprovalTicket(
                **{**ticket.__dict__, 'version': int(expected_version) + 1, 'fencing_token': max(int(ticket.fencing_token or 0), int(current.fencing_token or 0))}
            )
            self.tickets[str(ticket.action_id)] = updated
            return updated

    def record_approval(self, *, action_id: str, approver: str) -> ApprovalTicket:
        action_key = str(action_id).strip()
        approver_key = str(approver).strip()
        if not action_key or not approver_key:
            raise ValueError('action_id and approver are required')
        with self._lock:
            current = self.tickets.get(action_key, ApprovalTicket(action_id=action_key))
            approvals = tuple(dict.fromkeys([*current.approvals, approver_key]))
            required = max(int(current.required_approvals or 0), 2)
            state = current.state
            if current.state is not ApprovalWorkflowState.REJECTED:
                state = ApprovalWorkflowState.APPROVED if len(approvals) >= required else ApprovalWorkflowState.PARTIALLY_APPROVED
            ticket = ApprovalTicket(
                action_id=action_key,
                approvals=approvals,
                state=state,
                rejections=current.rejections,
                requested_by=current.requested_by,
                expires_at=current.expires_at,
                required_approvals=required,
                escalation_level=current.escalation_level,
                version=int(current.version) + 1,
                lease_owner=current.lease_owner,
                fencing_token=current.fencing_token,
            )
            self.tickets[action_key] = ticket
            return ticket

    def record_rejection(self, *, action_id: str, approver: str) -> ApprovalTicket:
        action_key = str(action_id).strip()
        approver_key = str(approver).strip()
        current = self.tickets.get(action_key, ApprovalTicket(action_id=action_key))
        rejections = tuple(dict.fromkeys([*current.rejections, approver_key]))
        ticket = ApprovalTicket(
            action_id=action_key,
            approvals=current.approvals,
            state=ApprovalWorkflowState.REJECTED,
            rejections=rejections,
            requested_by=current.requested_by,
            expires_at=current.expires_at,
            required_approvals=current.required_approvals,
            escalation_level=current.escalation_level,
            version=int(current.version) + 1,
            lease_owner=current.lease_owner,
            fencing_token=current.fencing_token,
        )
        self.tickets[action_key] = ticket
        return ticket

    def mark_executed(self, *, action_id: str) -> ApprovalTicket:
        action_key = str(action_id).strip()
        current = self.tickets.get(action_key, ApprovalTicket(action_id=action_key))
        executed = ApprovalTicket(
            action_id=current.action_id,
            approvals=current.approvals,
            state=ApprovalWorkflowState.EXECUTED,
            rejections=current.rejections,
            requested_by=current.requested_by,
            expires_at=current.expires_at,
            required_approvals=current.required_approvals,
            escalation_level=current.escalation_level,
            version=int(current.version) + 1,
            lease_owner=current.lease_owner,
            fencing_token=current.fencing_token,
        )
        self.tickets[action_key] = executed
        return executed


class SqliteApprovalRepository(PlatformSqliteApprovalRepository):
    """Safety-facing multi-step approval repository facade.

    SQLite ownership lives in runtime.platform.safety_approval_repository.
    """


__all__ = [
    'ApprovalRepository',
    'CANON_PLATFORM_SAFETY_APPROVAL_REPOSITORY',
    'CANON_SAFETY_APPROVAL_REPOSITORY',
    'InMemoryApprovalRepository',
    'SCHEMA_VERSION',
    'SqliteApprovalRepository',
]
