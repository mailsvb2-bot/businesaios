from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import TypeAlias

CANON_BILLING_DECIMAL_MONEY = True

DecimalInput: TypeAlias = Decimal | int | float | str

MONEY_QUANTUM = Decimal("0.01")
RATE_QUANTUM = Decimal("0.000001")
QUANTITY_QUANTUM = Decimal("0.000001")
MINOR_FACTOR = Decimal("100")
MINOR_QUANTUM = Decimal("1")


def _decimal(
    value: DecimalInput,
    *,
    name: str,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
    quantum: Decimal | None = None,
) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite decimal number")
    try:
        normalized = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{name} must be a finite decimal number") from exc
    if not normalized.is_finite():
        raise ValueError(f"{name} must be a finite decimal number")
    if minimum is not None and normalized < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and normalized > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    if quantum is not None:
        normalized = normalized.quantize(quantum, rounding=ROUND_HALF_UP)
    return normalized


def money_decimal(
    value: DecimalInput,
    *,
    name: str = "amount",
    allow_negative: bool = False,
) -> Decimal:
    return _decimal(
        value,
        name=name,
        minimum=None if allow_negative else Decimal("0"),
        quantum=MONEY_QUANTUM,
    )


def rate_decimal(
    value: DecimalInput,
    *,
    name: str = "rate",
    allow_negative: bool = False,
) -> Decimal:
    return _decimal(
        value,
        name=name,
        minimum=None if allow_negative else Decimal("0"),
        quantum=RATE_QUANTUM,
    )


def ratio_decimal(value: DecimalInput, *, name: str = "ratio") -> Decimal:
    return _decimal(
        value,
        name=name,
        minimum=Decimal("0"),
        maximum=Decimal("1"),
        quantum=RATE_QUANTUM,
    )


def quantity_decimal(
    value: DecimalInput,
    *,
    name: str = "quantity",
    allow_negative: bool = False,
) -> Decimal:
    return _decimal(
        value,
        name=name,
        minimum=None if allow_negative else Decimal("0"),
        quantum=QUANTITY_QUANTUM,
    )


def to_minor_units(
    value: DecimalInput,
    *,
    name: str = "amount",
    allow_negative: bool = False,
) -> int:
    normalized = money_decimal(
        value,
        name=name,
        allow_negative=allow_negative,
    )
    return int(normalized * MINOR_FACTOR)


def decimal_to_minor_units(
    value: DecimalInput,
    *,
    name: str = "amount",
    allow_negative: bool = False,
) -> int:
    """Round an unquantized decimal expression once at the money boundary."""

    normalized = _decimal(
        value,
        name=name,
        minimum=None if allow_negative else Decimal("0"),
    ).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    return int(normalized * MINOR_FACTOR)


def quantity_times_minor_units(
    quantity: DecimalInput,
    unit_amount_minor: int,
    *,
    quantity_name: str = "quantity",
    unit_name: str = "unit_amount_minor",
) -> int:
    if isinstance(unit_amount_minor, bool) or not isinstance(unit_amount_minor, int):
        raise ValueError(f"{unit_name} must be an integer")
    product = quantity_decimal(
        quantity,
        name=quantity_name,
        allow_negative=True,
    ) * Decimal(unit_amount_minor)
    return int(product.quantize(MINOR_QUANTUM, rounding=ROUND_HALF_UP))


def from_minor_units(value: int, *, name: str = "amount_minor") -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return (Decimal(value) / MINOR_FACTOR).quantize(
        MONEY_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def legacy_float(value: DecimalInput, *, name: str = "value") -> float:
    """Serialize an exact decimal at a legacy float boundary.

    Billing arithmetic must happen before this conversion. This helper exists
    only to preserve established DTO/API shapes while the repository migrates
    to minor-unit and decimal-native public contracts.
    """

    return float(_decimal(value, name=name))


def sum_money(values: list[DecimalInput] | tuple[DecimalInput, ...]) -> Decimal:
    total = sum(
        (money_decimal(value, allow_negative=True) for value in values),
        start=Decimal("0"),
    )
    return total.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def amounts_equal(left: DecimalInput, right: DecimalInput) -> bool:
    return money_decimal(left, allow_negative=True) == money_decimal(
        right,
        allow_negative=True,
    )


__all__ = [
    "CANON_BILLING_DECIMAL_MONEY",
    "DecimalInput",
    "MINOR_FACTOR",
    "MINOR_QUANTUM",
    "MONEY_QUANTUM",
    "QUANTITY_QUANTUM",
    "RATE_QUANTUM",
    "amounts_equal",
    "decimal_to_minor_units",
    "from_minor_units",
    "legacy_float",
    "money_decimal",
    "quantity_decimal",
    "quantity_times_minor_units",
    "rate_decimal",
    "ratio_decimal",
    "sum_money",
    "to_minor_units",
]
