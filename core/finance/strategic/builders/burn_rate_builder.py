from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2


class BurnRateBuilder:
    def build(self, cashflow: list[Decimal]) -> list[Decimal]:
        return [q2(abs(min(item, Decimal("0")))) for item in cashflow]
