from __future__ import annotations

from dataclasses import dataclass

from ..enums import BudgetPressureLevel, EconomicsSignalStatus
from ..types import BudgetEnvelope


@dataclass
class BudgetPressureEvaluator:
    def evaluate(self, budget: BudgetEnvelope) -> EconomicsSignalStatus:
        return {
            BudgetPressureLevel.LOW: EconomicsSignalStatus.HEALTHY,
            BudgetPressureLevel.MEDIUM: EconomicsSignalStatus.WARNING,
            BudgetPressureLevel.HIGH: EconomicsSignalStatus.CRITICAL,
            BudgetPressureLevel.EXTREME: EconomicsSignalStatus.CRITICAL,
        }.get(budget.pressure_level, EconomicsSignalStatus.UNKNOWN)
