from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from contracts.action_impact_contract import ActionExecutionContext, ActionImpact
from core.safety.operational.ports import OperationalBudgetLedgerPort

CANON_OPERATIONAL_BUDGET_ACCOUNTANT = True


@dataclass(frozen=True)
class BudgetAccountingEnvelope:
    tenant_id: str
    execution_id: str | None
    hour_bucket: str
    day_bucket: str
    actions_count: int
    budget_minor: int
    publications_count: int
    outbound_count: int
    strategic_changes_without_approval: int
    approval_required_without_human: int
    rollback_triggers: int


class OperationalBudgetAccountant:
    def to_envelope(self, ctx: ActionExecutionContext, impact: ActionImpact) -> BudgetAccountingEnvelope:
        now = self._coerce_now(ctx.payload.get("safety_now") or ctx.metadata.get("safety_now"))
        strategic_wo_approval = 0
        if int(impact.strategic_change_count) > 0 and not bool(ctx.payload.get("human_approved")):
            strategic_wo_approval = int(impact.strategic_change_count)

        approval_required_without_human = 0
        if bool(impact.requires_human_approval) and not bool(ctx.payload.get("human_approved")):
            approval_required_without_human = 1

        normalized_execution_id = None
        if ctx.execution_id is not None:
            text = str(ctx.execution_id).strip()
            normalized_execution_id = text or None

        return BudgetAccountingEnvelope(
            tenant_id=str(ctx.tenant_id),
            execution_id=normalized_execution_id,
            hour_bucket=now.strftime("%Y-%m-%dT%H"),
            day_bucket=now.strftime("%Y-%m-%d"),
            actions_count=1,
            budget_minor=int(impact.cost_minor),
            publications_count=int(impact.publication_count),
            outbound_count=int(impact.outbound_count),
            strategic_changes_without_approval=int(strategic_wo_approval),
            approval_required_without_human=int(approval_required_without_human),
            rollback_triggers=int(impact.rollback_event_count),
        )

    def commit(
        self,
        ledger: OperationalBudgetLedgerPort,
        envelope: BudgetAccountingEnvelope,
    ) -> None:
        ledger.commit(
            envelope.tenant_id,
            execution_id=envelope.execution_id,
            hour_bucket=envelope.hour_bucket,
            day_bucket=envelope.day_bucket,
            actions_count=envelope.actions_count,
            budget_minor=envelope.budget_minor,
            publications_count=envelope.publications_count,
            outbound_count=envelope.outbound_count,
            strategic_changes_without_approval=envelope.strategic_changes_without_approval,
            rollback_triggers=envelope.rollback_triggers,
        )

    @staticmethod
    def _coerce_now(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
        if isinstance(value, str) and value.strip():
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        return datetime.now(tz=UTC)


__all__ = [
    "BudgetAccountingEnvelope",
    "OperationalBudgetAccountant",
]