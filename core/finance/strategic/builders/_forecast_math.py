from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2


def geometric_series(base: Decimal, growth_rate: Decimal, periods: int) -> list[Decimal]:
    values: list[Decimal] = []
    current = base
    factor = Decimal("1") + growth_rate
    for _ in range(periods):
        values.append(q2(current))
        current = current * factor
    return values
