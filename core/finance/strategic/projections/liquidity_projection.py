from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2


class LiquidityProjection:
    def project(self, cash: Decimal, cashflow: list[Decimal]) -> list[Decimal]:
        balances: list[Decimal] = []
        current = cash
        for delta in cashflow:
            current = q2(current + delta)
            balances.append(current)
        return balances
