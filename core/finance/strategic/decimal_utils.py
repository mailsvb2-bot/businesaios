from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal("0.01")
FOURPLACES = Decimal("0.0001")


def to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def quantize_money(value: Decimal) -> Decimal:
    return to_decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def quantize_rate(value: Decimal) -> Decimal:
    return to_decimal(value).quantize(FOURPLACES, rounding=ROUND_HALF_UP)


def q2(value: object) -> Decimal:
    return quantize_money(to_decimal(value))
