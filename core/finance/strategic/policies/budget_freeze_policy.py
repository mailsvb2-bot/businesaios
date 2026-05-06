from __future__ import annotations

from decimal import Decimal


class BudgetFreezePolicy:
    def should_freeze(self, runway_months: Decimal, threshold: Decimal = Decimal('6')) -> bool:
        return runway_months < threshold
