from __future__ import annotations

"""Compatibility facade for the canonical finance decimal contract."""

from core.finance.money import (
    CANON_BILLING_DECIMAL_MONEY,
    DecimalInput,
    MINOR_FACTOR,
    MINOR_QUANTUM,
    MONEY_QUANTUM,
    QUANTITY_QUANTUM,
    RATE_QUANTUM,
    amounts_equal,
    decimal_to_minor_units,
    from_minor_units,
    legacy_float,
    money_decimal,
    quantity_decimal,
    quantity_times_minor_units,
    rate_decimal,
    ratio_decimal,
    sum_money,
    to_minor_units,
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
