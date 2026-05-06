from __future__ import annotations

from dataclasses import dataclass

from ..enums import GuardSeverity
from ..guard import GuardTrigger
from ..types import CashflowSignal


@dataclass
class CashflowRiskGuard:
    runway_warning_days: int = 90
    runway_block_days: int = 30

    def check(self, cashflow: CashflowSignal) -> GuardTrigger | None:
        if cashflow.runway_days is None:
            return GuardTrigger(code="cashflow_unknown", severity=GuardSeverity.WARNING, message="Cash runway is unknown.")
        if cashflow.runway_days < self.runway_block_days:
            return GuardTrigger(code="cashflow_risk", severity=GuardSeverity.BLOCK, message="Cash runway is below blocking threshold.", details={"runway_days": cashflow.runway_days})
        if cashflow.runway_days < self.runway_warning_days:
            return GuardTrigger(code="cashflow_risk", severity=GuardSeverity.WARNING, message="Cash runway is below safe operating threshold.", details={"runway_days": cashflow.runway_days})
        return None
