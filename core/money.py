"""Money helpers (canonical, deterministic).

Rules:
- Internal amounts may be stored in minor units (e.g., kopeks for RUB).
- UI text must never display raw minor units.
- This module contains ONLY pure helpers (no I/O).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Money:
    amount_minor: int
    currency: str = "RUB"

    @property
    def rub(self) -> int:
        if self.currency != "RUB":
            raise ValueError("ONLY_RUB_SUPPORTED")
        # Integer rubles, rounded toward zero.
        return int(self.amount_minor) // 100


def rub_to_minor(rub: int, *, currency: str = "RUB") -> int:
    if currency != "RUB":
        raise ValueError("ONLY_RUB_SUPPORTED")
    return int(rub) * 100


def minor_to_rub(minor: int, *, currency: str = "RUB") -> int:
    if currency != "RUB":
        raise ValueError("ONLY_RUB_SUPPORTED")
    return int(minor) // 100


def format_minor(minor: int, *, currency: str = "RUB") -> str:
    """Format minor amount for UI.

    For RUB: show integer rubles with the ₽ sign.
    """
    rub = minor_to_rub(minor, currency=currency)
    return f"{rub} ₽"
