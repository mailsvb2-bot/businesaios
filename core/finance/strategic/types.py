from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping

from config.final_hidden_logic_policy import DEFAULT_STRATEGIC_FINANCE_TYPE_POLICY

Money = Decimal
Rate = Decimal


@dataclass(frozen=True)
class FinancialInput:
    """Canonical strategic-finance input.

    This is an internal domain contract for strategic finance only.
    In BUSINESAIOS it must be built from the host economics snapshot rather than
    from a parallel finance snapshot path.
    """

    tenant_id: str
    correlation_id: str
    period_months: int
    revenue: Money
    costs: Money
    cash: Money
    debt: Money = DEFAULT_STRATEGIC_FINANCE_TYPE_POLICY.zero_money
    customers: int = 0
    new_customers: int = 0
    churn_rate: Rate = DEFAULT_STRATEGIC_FINANCE_TYPE_POLICY.zero_money
    gross_margin_rate: Rate = DEFAULT_STRATEGIC_FINANCE_TYPE_POLICY.zero_money
    growth_rate: Rate = DEFAULT_STRATEGIC_FINANCE_TYPE_POLICY.zero_money
    channel_spend: Mapping[str, Money] = field(default_factory=dict)
    channel_new_customers: Mapping[str, int] = field(default_factory=dict)
    assumptions: Mapping[str, Rate] = field(default_factory=dict)
    entities: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ForecastSnapshot:
    revenue: list[Money]
    costs: list[Money]
    margin: list[Money]
    cashflow: list[Money]
    burn_rate: list[Money]
    assumptions_version: str


@dataclass(frozen=True)
class Scenario:
    name: str
    revenue_multiplier: Rate = DEFAULT_STRATEGIC_FINANCE_TYPE_POLICY.one_multiplier
    cost_multiplier: Rate = DEFAULT_STRATEGIC_FINANCE_TYPE_POLICY.one_multiplier
    probability: Rate = DEFAULT_STRATEGIC_FINANCE_TYPE_POLICY.default_probability
    cash_pressure: Rate = DEFAULT_STRATEGIC_FINANCE_TYPE_POLICY.zero_money
    margin_deterioration: Rate = DEFAULT_STRATEGIC_FINANCE_TYPE_POLICY.zero_money
    channel_decay: Rate = DEFAULT_STRATEGIC_FINANCE_TYPE_POLICY.zero_money
    working_capital_pressure: Rate = DEFAULT_STRATEGIC_FINANCE_TYPE_POLICY.zero_money
    downside_risk: Rate = DEFAULT_STRATEGIC_FINANCE_TYPE_POLICY.zero_money
    capital_efficiency_bias: Rate = DEFAULT_STRATEGIC_FINANCE_TYPE_POLICY.zero_money
    notes: tuple[str, ...] = ()
    channel_bias: Mapping[str, Rate] = field(default_factory=dict)
    segment_bias: Mapping[str, Rate] = field(default_factory=dict)
    product_bias: Mapping[str, Rate] = field(default_factory=dict)
    entity_bias: Mapping[str, Rate] = field(default_factory=dict)
    entity_scope: tuple[str, ...] = ()
    downside_tree: tuple[str, ...] = ()
    downside_tree_weights: Mapping[str, Rate] = field(default_factory=dict)
    working_capital_dynamics: Mapping[str, Rate] = field(default_factory=dict)


@dataclass(frozen=True)
class AllocationRecommendation:
    allocations: Mapping[str, Money]
    rationale: tuple[str, ...] = ()


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    code: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionTrace:
    decision_id: str
    objective: str
    selected_scenario: str
    selected_allocation: Mapping[str, Money]
    guard_codes: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
