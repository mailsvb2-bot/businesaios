from __future__ import annotations

from dataclasses import dataclass

from core.safety.operational.operational_budget_accountant import BudgetAccountingEnvelope
from core.safety.operational.ports import OperationalBudgetLedgerPort
from core.safety.operational.tenant_policy_provider import TenantOperationalBudgetPolicyProvider

CANON_OPERATIONAL_BUDGET_GUARD = True


@dataclass(frozen=True)
class OperationalBudgetDecision:
    status: str
    reason: str
    details: dict[str, object]


class OperationalBudgetGuard:
    def __init__(
        self,
        ledger: OperationalBudgetLedgerPort,
        policy_source: TenantOperationalBudgetPolicyProvider | None = None,
        *,
        policy_provider: TenantOperationalBudgetPolicyProvider | None = None,
    ) -> None:
        resolved_policy_source = policy_source or policy_provider
        if resolved_policy_source is None:
            raise ValueError("policy_source is required")
        self._ledger = ledger
        self._policy_source = resolved_policy_source

    def evaluate(self, envelope: BudgetAccountingEnvelope) -> OperationalBudgetDecision:
        if int(envelope.approval_required_without_human) > 0:
            return OperationalBudgetDecision(
                status="block",
                reason="human_approval_required",
                details={
                    "hour_bucket": envelope.hour_bucket,
                    "day_bucket": envelope.day_bucket,
                },
            )

        policy = self._policy_source.for_tenant(envelope.tenant_id)
        hourly = self._ledger.get_hour(envelope.tenant_id, envelope.hour_bucket)
        daily = self._ledger.get_day(envelope.tenant_id, envelope.day_bucket)

        next_actions_per_hour = int(hourly.actions_count) + int(envelope.actions_count)
        next_actions_per_day = int(daily.actions_count) + int(envelope.actions_count)
        next_budget_minor_per_day = int(daily.budget_minor) + int(envelope.budget_minor)
        next_publications_per_day = int(daily.publications_count) + int(envelope.publications_count)
        next_outbound_per_day = int(daily.outbound_count) + int(envelope.outbound_count)
        next_strategy_wo_approval_per_day = (
            int(daily.strategic_changes_without_approval) + int(envelope.strategic_changes_without_approval)
        )
        next_rollbacks_per_day = int(daily.rollback_triggers) + int(envelope.rollback_triggers)

        exceeded = {
            "max_actions_per_hour": next_actions_per_hour > int(policy.max_actions_per_hour),
            "max_actions_per_day": next_actions_per_day > int(policy.max_actions_per_day),
            "max_budget_minor_per_day": next_budget_minor_per_day > int(policy.max_budget_minor_per_day),
            "max_new_publications_per_day": next_publications_per_day > int(policy.max_new_publications_per_day),
            "max_outbound_messages_per_day": next_outbound_per_day > int(policy.max_outbound_messages_per_day),
            "max_strategic_changes_without_human_approval_per_day": (
                next_strategy_wo_approval_per_day
                > int(policy.max_strategic_changes_without_human_approval_per_day)
            ),
            "max_rollback_triggers_per_day": next_rollbacks_per_day > int(policy.max_rollback_triggers_per_day),
        }

        if any(exceeded.values()):
            return OperationalBudgetDecision(
                status="block",
                reason="operational_budget_exceeded",
                details={
                    "next": {
                        "actions_per_hour": next_actions_per_hour,
                        "actions_per_day": next_actions_per_day,
                        "budget_minor_per_day": next_budget_minor_per_day,
                        "publications_per_day": next_publications_per_day,
                        "outbound_per_day": next_outbound_per_day,
                        "strategic_changes_without_approval_per_day": next_strategy_wo_approval_per_day,
                        "rollback_triggers_per_day": next_rollbacks_per_day,
                    },
                    "limits": {
                        "max_actions_per_hour": policy.max_actions_per_hour,
                        "max_actions_per_day": policy.max_actions_per_day,
                        "max_budget_minor_per_day": policy.max_budget_minor_per_day,
                        "max_new_publications_per_day": policy.max_new_publications_per_day,
                        "max_outbound_messages_per_day": policy.max_outbound_messages_per_day,
                        "max_strategic_changes_without_human_approval_per_day": (
                            policy.max_strategic_changes_without_human_approval_per_day
                        ),
                        "max_rollback_triggers_per_day": policy.max_rollback_triggers_per_day,
                    },
                    "exceeded": exceeded,
                },
            )

        return OperationalBudgetDecision(
            status="allow",
            reason="operational_budget_ok",
            details={
                "hour_bucket": envelope.hour_bucket,
                "day_bucket": envelope.day_bucket,
            },
        )


__all__ = [
    "OperationalBudgetDecision",
    "OperationalBudgetGuard",
]
