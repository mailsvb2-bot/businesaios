from __future__ import annotations

from dataclasses import dataclass, field

from ..guard import GuardTrigger
from ..guards.advisory_boundary_guard import AdvisoryBoundaryGuard
from ..guards.budget_integrity_guard import BudgetIntegrityGuard
from ..guards.cashflow_risk_guard import CashflowRiskGuard
from ..guards.currency_consistency_guard import CurrencyConsistencyGuard
from ..guards.negative_margin_guard import NegativeMarginGuard
from ..guards.overspend_guard import OverspendGuard
from ..guards.signal_period_guard import SignalPeriodGuard
from ..types import BudgetEnvelope, CashflowSignal, EconomicsReadModel, MarginSnapshot, SpendSignal


@dataclass
class EconomicsGuardReportBuilder:
    signal_period_guard: SignalPeriodGuard = field(default_factory=SignalPeriodGuard)
    currency_consistency_guard: CurrencyConsistencyGuard = field(default_factory=CurrencyConsistencyGuard)
    negative_margin_guard: NegativeMarginGuard = field(default_factory=NegativeMarginGuard)
    overspend_guard: OverspendGuard = field(default_factory=OverspendGuard)
    cashflow_risk_guard: CashflowRiskGuard = field(default_factory=CashflowRiskGuard)
    budget_integrity_guard: BudgetIntegrityGuard = field(default_factory=BudgetIntegrityGuard)
    advisory_boundary_guard: AdvisoryBoundaryGuard = field(default_factory=AdvisoryBoundaryGuard)

    def build(
        self,
        *,
        read_model: EconomicsReadModel,
        margin: MarginSnapshot,
        spend: SpendSignal,
        budget: BudgetEnvelope,
        cashflow: CashflowSignal,
        policy_advice: dict,
    ) -> list[GuardTrigger]:
        triggers: list[GuardTrigger] = []
        for trigger in (
            self.signal_period_guard.check(read_model),
            self.currency_consistency_guard.check(read_model),
            self.negative_margin_guard.check(margin),
            self.overspend_guard.check(spend, budget),
            self.cashflow_risk_guard.check(cashflow),
            self.budget_integrity_guard.check(budget),
            self.advisory_boundary_guard.check(policy_advice),
        ):
            if trigger is not None:
                triggers.append(trigger)
        return triggers
