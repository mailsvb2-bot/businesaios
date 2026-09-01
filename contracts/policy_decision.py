from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contracts.action_intent import ActionIntentV1

CANON_POLICY_DECISION_CONTRACT = True


@dataclass(frozen=True)
class PolicyDecisionV1:
    tier: str
    action_type: str
    action_class: str
    allowed: bool
    approval_required: bool
    blocked_by_policy: bool
    handoff_reason: str | None = None
    intent_id: str = ""
    decision_id: str = ""
    tenant_id: str = ""
    business_id: str = ""
    schema_version: int = 1

    @property
    def verdict(self) -> str:
        if self.blocked_by_policy:
            return "denied"
        if self.approval_required:
            return "approval_required"
        return "allowed" if self.allowed else "not_authorized"

    def bind_intent(self, intent: ActionIntentV1) -> PolicyDecisionV1:
        return replace(
            self,
            intent_id=intent.intent_id,
            decision_id=intent.decision_id,
            tenant_id=intent.tenant_id,
            business_id=intent.business_id,
        )


__all__ = ["CANON_POLICY_DECISION_CONTRACT", "PolicyDecisionV1"]
