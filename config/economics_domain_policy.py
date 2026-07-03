from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class EconomicsSignalDefaults:
    default_currency: str = "USD"
    default_retention_probability: float = 0.0
    default_revenue: float = 0.0
    default_cost: float = 0.0
    zero_amount: float = 0.0
    retention_probability_floor: float = 0.0
    retention_probability_ceiling: float = 1.0


@dataclass(frozen=True)
class EconomicBrainPolicy:
    retention_discount_threshold: float = 0.3
    retention_upsell_threshold: float = 0.7
    discount_value: float = 0.15
    upsell_value: float = 0.10
    keep_value: float = 0.0
    stabilize_value: float = 0.20
    expand_value: float = 0.15
    optimize_value: float = 0.0
    reward_floor: float = 0.0
    penalty_multiplier: float = 0.0


@dataclass(frozen=True)
class LTVEstimatorPolicy:
    zero_value: float = 0.0


@dataclass(frozen=True)
class CapitalAllocationPolicy:
    reserve_ratio: float = 0.2
    min_runway_days: int = 30
    shutdown_risk_threshold: float = 0.8
    reserve_horizon_days: int = 60
    active_horizon_days: int = 30
    logistic_floor: float = -60.0
    logistic_ceiling: float = 60.0
    growth_share_min: float = 0.2
    growth_share_max: float = 0.8
    reserve_target: str = "reserve"
    growth_target: str = "growth"
    cash_capital_type: str = "cash"
    minimal_risk_class: str = "minimal"
    managed_risk_class: str = "managed"
    zero_value: float = 0.0
    one_value: float = 1.0
    runway_days_floor: float = 1.0
    value_margin_offset: float = 1.0


@dataclass(frozen=True)
class BudgetEnvelopePolicy:
    zero_budget: float = 0.0
    zero_reserve: float = 0.0
    ltv_cac_medium_ratio: float = 3.0
    extreme_pressure: str = "extreme"
    high_pressure: str = "high"
    medium_pressure: str = "medium"
    low_pressure: str = "low"


@dataclass(frozen=True)
class EconomicsMathPolicy:
    zero_value: float = 0.0


DEFAULT_ECONOMICS_SIGNAL_DEFAULTS = EconomicsSignalDefaults()
DEFAULT_ECONOMIC_BRAIN_POLICY = EconomicBrainPolicy()
DEFAULT_LTV_ESTIMATOR_POLICY = LTVEstimatorPolicy()
DEFAULT_CAPITAL_ALLOCATION_POLICY = CapitalAllocationPolicy()
DEFAULT_BUDGET_ENVELOPE_POLICY = BudgetEnvelopePolicy()
DEFAULT_ECONOMICS_MATH_POLICY = EconomicsMathPolicy()
