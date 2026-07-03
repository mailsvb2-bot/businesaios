from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class BudgetEnvelopeBuilderPolicy:
    zero_amount: float = 0.0
    reserve_ratio: float = 0.35
    minimum_budget_ratio_of_cash: float = 0.05
    medium_pressure_spend_multiple: float = 2.0
    minimum_free_cash_threshold: float = 1.0
    low_pressure_multiplier: float = 1.0
    medium_pressure_multiplier: float = 0.8
    high_pressure_multiplier: float = 0.5
    extreme_pressure_multiplier: float = 0.2


DEFAULT_BUDGET_ENVELOPE_BUILDER_POLICY = BudgetEnvelopeBuilderPolicy()
