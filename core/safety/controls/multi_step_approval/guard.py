from __future__ import annotations

from datetime import datetime, timezone

from ..action_catalog import ActionSafetyCatalog, build_default_action_catalog
from ..action_context import SafetyActionContext
from ..action_identity import canonical_action_id
from ..control_result import ControlDecision, ControlStatus
from .approval_escalation import ApprovalEscalationEngine
from .models import ApprovalPolicy, ApprovalWorkflowState
from .repository import ApprovalRepository


class MultiStepApprovalGuard:
    control_name = "multi_step_approval"

    def __init__(self, repository: ApprovalRepository, policy: ApprovalPolicy, catalog: ActionSafetyCatalog | None = None, escalation: ApprovalEscalationEngine | None = None):
        self._repository = repository
        self._policy = policy
        self._catalog = catalog or build_default_action_catalog()
        self._escalation = escalation or ApprovalEscalationEngine()

    def evaluate(self, ctx: SafetyActionContext) -> ControlDecision:
        payload = dict(ctx.payload)
        spec = self._catalog.resolve(ctx.action)
        requires_explicit = bool(payload.get("requires_multi_step_approval") or payload.get("approval_required"))
        requires_by_prefix = bool(self._policy.action_prefixes) and any(str(ctx.action).startswith(prefix) for prefix in self._policy.action_prefixes)
        requires_by_catalog = bool(getattr(spec, "approval_required", False))
        if not requires_explicit and not requires_by_prefix and not requires_by_catalog:
            return ControlDecision(control=self.control_name, status=ControlStatus.ALLOW, reason="approval_not_required")
        action_id = canonical_action_id(action=ctx.action, tenant_id=ctx.tenant_id, payload=payload)
        ticket = self._escalation.apply(self._repository.get(action_id), base_required=self._policy.min_approvals)
        try:
            self._repository.put(ticket)
        except Exception:
            pass
        if ticket.state is ApprovalWorkflowState.REJECTED:
            return ControlDecision(control=self.control_name, status=ControlStatus.BLOCK, reason='approval_rejected', details={'action_id': action_id, 'rejections': list(ticket.rejections)})
        if ticket.state is ApprovalWorkflowState.SUPERSEDED:
            return ControlDecision(control=self.control_name, status=ControlStatus.BLOCK, reason='approval_superseded', details={'action_id': action_id})
        if ticket.state is ApprovalWorkflowState.CANCELLED:
            return ControlDecision(control=self.control_name, status=ControlStatus.BLOCK, reason='approval_cancelled', details={'action_id': action_id})
        if ticket.state is ApprovalWorkflowState.EXPIRED:
            return ControlDecision(control=self.control_name, status=ControlStatus.BLOCK, reason='approval_expired', details={'action_id': action_id})
        if ticket.expires_at:
            try:
                expiry = datetime.fromisoformat(str(ticket.expires_at))
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry <= datetime.now(timezone.utc):
                    return ControlDecision(control=self.control_name, status=ControlStatus.BLOCK, reason='approval_expired', details={'action_id': action_id})
            except Exception:
                pass
        required_approvals = max(int(self._policy.min_approvals), int(ticket.required_approvals or 0))
        if len(ticket.approvals) < required_approvals:
            return ControlDecision(
                control=self.control_name,
                status=ControlStatus.BLOCK,
                reason="insufficient_approvals",
                details={"action_id": action_id, "approvals": list(ticket.approvals), "required": required_approvals, 'state': str(ticket.state.value if hasattr(ticket.state, 'value') else ticket.state)},
            )
        return ControlDecision(control=self.control_name, status=ControlStatus.ALLOW, reason="approvals_satisfied", details={"action_id": action_id, 'state': str(ticket.state.value if hasattr(ticket.state, 'value') else ticket.state)})
