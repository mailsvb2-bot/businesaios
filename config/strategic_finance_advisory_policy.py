from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

CANON_COMPAT_SHIM = True


@dataclass(frozen=True)
class StrategicFinanceAdvisoryPolicyDefaults:
    max_channel_share: Decimal = Decimal('0.6')
    zero_cash_buffer: Decimal = Decimal('0')
    runway_guard_floor_months: Decimal = Decimal('6')
    downside_weight_when_protected: Decimal = Decimal('1.25')
    downside_weight_balanced: Decimal = Decimal('1.0')
    max_scored_runway_months: Decimal = Decimal('36')
    runway_bonus_denominator_months: Decimal = Decimal('12')
    debt_penalty_revenue_floor: Decimal = Decimal('1')
    zero_debt_penalty: Decimal = Decimal('0')
    liquidity_tail_window: int = 3
    liquidity_tail_default: Decimal = Decimal('0')
    liquidity_protection_runway_months: Decimal = Decimal('4')
    capital_preservation_runway_months: Decimal = Decimal('8')
    cash_pressure_rejection_runway_months: Decimal = Decimal('6')
    cash_pressure_rejection_threshold: Decimal = Decimal('0.20')
    downside_risk_rejection_runway_months: Decimal = Decimal('4')
    downside_risk_rejection_threshold: Decimal = Decimal('0.22')
    downside_tree_rejection_weight_sum: Decimal = Decimal('0.20')
    downside_tree_rejection_runway_months: Decimal = Decimal('8')
    comparison_note_limit: int = 2
    scenario_score_precision: int = 2
    liquidity_mode_protection: str = 'liquidity_protection'
    liquidity_mode_preservation: str = 'capital_preservation'
    liquidity_mode_balanced: str = 'balanced_growth'
    objective: str = 'extend runway while preserving efficient growth'


DEFAULT_STRATEGIC_FINANCE_ADVISORY_POLICY = StrategicFinanceAdvisoryPolicyDefaults()
