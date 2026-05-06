from __future__ import annotations

from dataclasses import dataclass

from ..enums import GuardSeverity
from ..guard import GuardTrigger
from ..types import EconomicsReadModel


@dataclass
class CurrencyConsistencyGuard:
    def check(self, read_model: EconomicsReadModel) -> GuardTrigger | None:
        currencies = {
            "revenue": read_model.revenue.currency,
            "cost": read_model.cost.currency,
            "spend": read_model.spend.currency,
            "cashflow": read_model.cashflow.currency,
        }
        if len(set(currencies.values())) > 1:
            return GuardTrigger(code="currency_mismatch", severity=GuardSeverity.BLOCK, message="Economics signals use inconsistent currencies.", details=currencies)
        return None
