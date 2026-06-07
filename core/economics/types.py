from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from config.economics_domain_policy import DEFAULT_ECONOMICS_MATH_POLICY, DEFAULT_ECONOMICS_SIGNAL_DEFAULTS

from .enums import BudgetPressureLevel, EconomicsSignalStatus, MarginHealthStatus, PaybackRiskLevel
from .guard import GuardTrigger
from .ids import EconomicsSnapshotId


@dataclass(frozen=True)
class EconomicState:
    retention_prob: float
    revenue: float
    cost: float

    @staticmethod
    def from_world_economy(economy: dict[str, Any] | None) -> EconomicState:
        economy = dict(economy or {})
        defaults = DEFAULT_ECONOMICS_SIGNAL_DEFAULTS
        rp = max(
            float(DEFAULT_ECONOMICS_SIGNAL_DEFAULTS.retention_probability_floor),
            min(
                float(DEFAULT_ECONOMICS_SIGNAL_DEFAULTS.retention_probability_ceiling),
                float(economy.get("retention_prob") or defaults.default_retention_probability),
            ),
        )
        revenue = float(economy.get("revenue") or defaults.default_revenue or DEFAULT_ECONOMICS_MATH_POLICY.zero_value)
        cost = float(economy.get("cost") or defaults.default_cost or DEFAULT_ECONOMICS_MATH_POLICY.zero_value)
        return EconomicState(retention_prob=rp, revenue=revenue, cost=cost)


@dataclass(frozen=True)
class EconomicAction:
    kind: str
    value: float


@dataclass(frozen=True)
class UnitEconomicsSnapshot:
    tenant_id: str
    cac: float
    ltv: float
    margin: float


@dataclass(frozen=True)
class RevenueSignal:
    period_days: int
    gross_revenue: float
    net_revenue: float
    orders: int
    currency: str = DEFAULT_ECONOMICS_SIGNAL_DEFAULTS.default_currency


@dataclass(frozen=True)
class CostSignal:
    period_days: int
    cogs: float
    fixed_costs: float
    variable_costs: float
    currency: str = DEFAULT_ECONOMICS_SIGNAL_DEFAULTS.default_currency


@dataclass(frozen=True)
class SpendSignal:
    period_days: int
    marketing_spend: float
    sales_spend: float
    operations_spend: float
    currency: str = DEFAULT_ECONOMICS_SIGNAL_DEFAULTS.default_currency


@dataclass(frozen=True)
class CustomerValueSignal:
    active_customers: int
    new_customers: int
    returning_customers: int
    average_order_value: float
    purchase_frequency_30d: float
    gross_retention_30d: float
    contribution_margin_ratio: float | None = None


@dataclass(frozen=True)
class CashflowSignal:
    cash_in: float
    cash_out: float
    runway_days: int | None
    unrestricted_cash: float
    currency: str = DEFAULT_ECONOMICS_SIGNAL_DEFAULTS.default_currency


@dataclass(frozen=True)
class EconomicsReadModel:
    revenue: RevenueSignal
    cost: CostSignal
    spend: SpendSignal
    customer_value: CustomerValueSignal
    cashflow: CashflowSignal


@dataclass(frozen=True)
class UnitEconomics:
    gross_profit: float
    contribution_profit: float
    contribution_margin_ratio: float
    revenue_per_customer: float
    contribution_per_customer_period: float
    contribution_per_customer_day: float
    variable_cost_ratio: float
    period_days: int


@dataclass(frozen=True)
class MarginSnapshot:
    gross_margin_ratio: float
    net_margin_ratio: float
    status: MarginHealthStatus


@dataclass(frozen=True)
class BudgetEnvelope:
    available_growth_budget: float
    protected_cash_reserve: float
    recommended_spend_cap: float
    pressure_level: BudgetPressureLevel


@dataclass(frozen=True)
class PaybackSnapshot:
    cac_payback_days: float | None
    risk_level: PaybackRiskLevel


@dataclass(frozen=True)
class LTVSnapshot:
    ltv: float | None
    assumptions: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CACSnapshot:
    blended_cac: float | None
    attributed_new_customers: int | None = None


@dataclass(frozen=True)
class EconomicsEvaluation:
    budget_pressure_status: EconomicsSignalStatus
    margin_health_status: EconomicsSignalStatus
    ltv_cac_status: EconomicsSignalStatus
    payback_risk_status: EconomicsSignalStatus
    scores: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class BudgetAllocationAdvice:
    total_recommended_budget: float
    channel_allocations: dict[str, float]
    rationale: str


@dataclass(frozen=True)
class SpendCapAdvice:
    hard_cap: float
    soft_cap: float
    rationale: str


@dataclass(frozen=True)
class RiskBudgetAdvice:
    experiment_budget: float
    core_budget: float
    reserve_budget: float
    rationale: str


@dataclass(frozen=True)
class EconomicsSnapshot:
    snapshot_id: EconomicsSnapshotId
    built_at: datetime
    read_model: EconomicsReadModel
    unit_economics: UnitEconomics
    margin: MarginSnapshot
    budget_envelope: BudgetEnvelope
    payback: PaybackSnapshot
    ltv: LTVSnapshot
    cac: CACSnapshot
    evaluation: EconomicsEvaluation
    guard_triggers: list[GuardTrigger] = field(default_factory=list)
    explanations: dict[str, str] = field(default_factory=dict)
    policy_advice: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_blocking_guard(self) -> bool:
        return any(trigger.is_blocking for trigger in self.guard_triggers)
