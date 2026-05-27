from __future__ import annotations

from dataclasses import dataclass

from contracts.action_impact_contract import ActionExecutionContext, ActionImpact
from core.safety.operational.action_impact_builder import ActionImpactBuilder
from core.safety.operational.operational_budget_accountant import (
    BudgetAccountingEnvelope,
    OperationalBudgetAccountant,
)
from core.safety.operational.operational_budget_guard import (
    OperationalBudgetDecision,
    OperationalBudgetGuard,
)
from core.safety.operational.ports import OperationalBudgetLedgerPort

CANON_OPERATIONAL_BUDGET_SERVICE = True


@dataclass(frozen=True)
class PrecheckResult:
    impact: ActionImpact
    envelope: BudgetAccountingEnvelope
    decision: OperationalBudgetDecision


class OperationalBudgetService:
    def __init__(
        self,
        impact_builder: ActionImpactBuilder,
        accountant: OperationalBudgetAccountant,
        guard: OperationalBudgetGuard,
        ledger: OperationalBudgetLedgerPort,
    ) -> None:
        self._impact_builder = impact_builder
        self._accountant = accountant
        self._guard = guard
        self._ledger = ledger

    def precheck(self, ctx: ActionExecutionContext) -> PrecheckResult:
        impact = self._impact_builder.build(ctx)
        envelope = self._accountant.to_envelope(ctx, impact)
        decision = self._guard.evaluate(envelope)
        return PrecheckResult(
            impact=impact,
            envelope=envelope,
            decision=decision,
        )

    def commit(self, envelope: BudgetAccountingEnvelope) -> None:
        self._accountant.commit(self._ledger, envelope)


__all__ = [
    "OperationalBudgetService",
    "PrecheckResult",
]