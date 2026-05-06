from __future__ import annotations

from dataclasses import dataclass

from ..enums import GuardSeverity
from ..guard import GuardTrigger
from ..types import EconomicsReadModel


@dataclass
class SignalPeriodGuard:
    def check(self, read_model: EconomicsReadModel) -> GuardTrigger | None:
        periods = {
            "revenue": read_model.revenue.period_days,
            "cost": read_model.cost.period_days,
            "spend": read_model.spend.period_days,
        }
        if len(set(periods.values())) > 1:
            return GuardTrigger(code="signal_period_mismatch", severity=GuardSeverity.BLOCK, message="Economics signals use inconsistent period lengths.", details=periods)
        return None
