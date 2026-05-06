from __future__ import annotations

from dataclasses import dataclass, field, replace

from config.economics_builder_policy import DEFAULT_BUDGET_ENVELOPE_BUILDER_POLICY, BudgetEnvelopeBuilderPolicy

from ..enums import BudgetPressureLevel
from ..types import BudgetEnvelope, CashflowSignal, MarginSnapshot, SpendSignal


@dataclass
class BudgetEnvelopeBuilder:
    reserve_ratio: float | None = None
    minimum_budget_ratio_of_cash: float | None = None
    policy: BudgetEnvelopeBuilderPolicy = field(default_factory=lambda: DEFAULT_BUDGET_ENVELOPE_BUILDER_POLICY)

    def __post_init__(self) -> None:
        override_reserve_ratio = self.policy.reserve_ratio if self.reserve_ratio is None else self.reserve_ratio
        override_minimum_budget_ratio_of_cash = (
            self.policy.minimum_budget_ratio_of_cash
            if self.minimum_budget_ratio_of_cash is None
            else self.minimum_budget_ratio_of_cash
        )
        self.policy = replace(
            self.policy,
            reserve_ratio=override_reserve_ratio,
            minimum_budget_ratio_of_cash=override_minimum_budget_ratio_of_cash,
        )
        self.reserve_ratio = self.policy.reserve_ratio
        self.minimum_budget_ratio_of_cash = self.policy.minimum_budget_ratio_of_cash

    def build(self, *, cashflow: CashflowSignal, spend: SpendSignal, margin: MarginSnapshot) -> BudgetEnvelope:
        policy = self.policy
        unrestricted_cash = max(cashflow.unrestricted_cash, policy.zero_amount)
        protected_cash_reserve = unrestricted_cash * policy.reserve_ratio
        free_cash = max(unrestricted_cash - protected_cash_reserve, policy.zero_amount)
        recent_total_spend = spend.marketing_spend + spend.sales_spend + spend.operations_spend
        if unrestricted_cash <= policy.zero_amount:
            pressure = BudgetPressureLevel.EXTREME
        elif margin.net_margin_ratio < policy.zero_amount or free_cash < recent_total_spend:
            pressure = BudgetPressureLevel.HIGH
        elif free_cash < max(recent_total_spend * policy.medium_pressure_spend_multiple, policy.minimum_free_cash_threshold):
            pressure = BudgetPressureLevel.MEDIUM
        else:
            pressure = BudgetPressureLevel.LOW
        multiplier = {
            BudgetPressureLevel.LOW: policy.low_pressure_multiplier,
            BudgetPressureLevel.MEDIUM: policy.medium_pressure_multiplier,
            BudgetPressureLevel.HIGH: policy.high_pressure_multiplier,
            BudgetPressureLevel.EXTREME: policy.extreme_pressure_multiplier,
        }[pressure]
        available_growth_budget = max(free_cash * multiplier, policy.zero_amount)
        baseline_cap = max(recent_total_spend, unrestricted_cash * policy.minimum_budget_ratio_of_cash)
        recommended_spend_cap = max(min(available_growth_budget, baseline_cap), policy.zero_amount)
        return BudgetEnvelope(
            available_growth_budget=available_growth_budget,
            protected_cash_reserve=protected_cash_reserve,
            recommended_spend_cap=recommended_spend_cap,
            pressure_level=pressure,
        )
