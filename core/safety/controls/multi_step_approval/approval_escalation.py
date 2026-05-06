from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from .models import ApprovalTicket, ApprovalWorkflowState

CANON_SAFETY_APPROVAL_ESCALATION = True


class ApprovalEscalationEngine:
    def __init__(self, *, escalation_window_minutes: int = 15, max_extra_approvals: int = 1) -> None:
        self._escalation_window_minutes = max(1, int(escalation_window_minutes))
        self._max_extra_approvals = max(0, int(max_extra_approvals))

    def apply(self, ticket: ApprovalTicket, *, base_required: int, now: datetime | None = None) -> ApprovalTicket:
        current = ticket
        instant = now or datetime.now(timezone.utc)
        required = max(int(base_required), int(ticket.required_approvals or 0))
        approvals = len(tuple(ticket.approvals or ()))
        if ticket.state in {
            ApprovalWorkflowState.EXECUTED,
            ApprovalWorkflowState.REJECTED,
            ApprovalWorkflowState.CANCELLED,
            ApprovalWorkflowState.SUPERSEDED,
        }:
            return replace(ticket, required_approvals=required)
        if ticket.expires_at:
            try:
                expiry = datetime.fromisoformat(str(ticket.expires_at))
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry <= instant and ticket.state in {
                    ApprovalWorkflowState.PENDING,
                    ApprovalWorkflowState.REQUESTED,
                    ApprovalWorkflowState.PARTIALLY_APPROVED,
                }:
                    return replace(ticket, state=ApprovalWorkflowState.EXPIRED, required_approvals=required)
                if expiry - instant <= timedelta(minutes=self._escalation_window_minutes) and approvals < required:
                    escalated = min(required + self._max_extra_approvals, required + 1)
                    current = replace(
                        ticket,
                        required_approvals=escalated,
                        escalation_level=max(1, int(ticket.escalation_level or 0) + 1),
                    )
                    required = escalated
            except Exception:
                current = replace(ticket, required_approvals=required)
        if approvals == 0 and current.state is ApprovalWorkflowState.PENDING:
            return replace(current, state=ApprovalWorkflowState.REQUESTED, required_approvals=required)
        if 0 < approvals < required and current.state not in {ApprovalWorkflowState.REJECTED, ApprovalWorkflowState.EXPIRED}:
            return replace(current, state=ApprovalWorkflowState.PARTIALLY_APPROVED, required_approvals=required)
        if approvals >= required and current.state not in {ApprovalWorkflowState.REJECTED, ApprovalWorkflowState.EXPIRED}:
            return replace(current, state=ApprovalWorkflowState.APPROVED, required_approvals=required)
        return replace(current, required_approvals=required)


__all__ = ['ApprovalEscalationEngine', 'CANON_SAFETY_APPROVAL_ESCALATION']
