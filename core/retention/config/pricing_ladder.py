from __future__ import annotations

"""Canonical retention pricing ladder contract.

This module is the single source of truth for retention pricing primitives:
- base price keys and defaults
- allowed discounts
- offer windows
- arm -> price/window mappings

Compat modules may re-export these values, but must not redefine them.
"""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class OfferWindow:
    day_from: int
    day_to: int


# Base prices (RUB)
BASE_PRICES_RUB: Final[dict[str, int]] = {
    "p14": 10_000,
    "p30": 14_900,
    "p90": 21_900,
    "bundle_14_30": 24_900,
    "bundle_30_90": 34_900,
}


# Allowed discounts (percent) – AI can only choose from here.
ALLOWED_DISCOUNTS_PCT: Final[tuple[int, ...]] = (0, 10, 15, 20)


# Offer windows (day_index is your program day; keep deterministic)
WINDOWS: Final[dict[str, OfferWindow]] = {
    "offer_90": OfferWindow(day_from=35, day_to=55),
    "offer_bundle": OfferWindow(day_from=15, day_to=365),
    "offer_30": OfferWindow(day_from=1, day_to=365),
}


_ARM_PRICE_KEYS: Final[dict[str, str]] = {
    "offer_30_14900": "p30",
    "offer_90_21900": "p90",
    "offer_bundle_14_30": "bundle_14_30",
}

_ARM_WINDOW_KEYS: Final[dict[str, str]] = {
    "offer_30_14900": "offer_30",
    "offer_90_21900": "offer_90",
    "offer_bundle_14_30": "offer_bundle",
}


def default_price_for_key(price_key: str) -> int | None:
    key = str(price_key or "").strip()
    if not key:
        return None
    value = BASE_PRICES_RUB.get(key)
    return int(value) if value is not None else None


def price_key_for_arm(offer_arm: str) -> str | None:
    arm = str(offer_arm or "").strip()
    if not arm:
        return None
    return _ARM_PRICE_KEYS.get(arm)


def base_price_for_arm(offer_arm: str, *, prices: dict | None = None) -> int | None:
    key = price_key_for_arm(offer_arm)
    if not key:
        return None
    if isinstance(prices, dict) and key in prices and prices.get(key) is not None:
        return int(prices[key])
    return default_price_for_key(key)


def window_key_for_arm(offer_arm: str) -> str | None:
    arm = str(offer_arm or "").strip()
    if not arm:
        return None
    return _ARM_WINDOW_KEYS.get(arm)


def window_for_arm(offer_arm: str) -> OfferWindow | None:
    win_key = window_key_for_arm(offer_arm)
    if not win_key:
        return None
    return WINDOWS.get(win_key)


def retention_boot_prices() -> dict[str, int]:
    return {
        "p30": int(BASE_PRICES_RUB.get("p30", 14_900)),
        "p90": int(BASE_PRICES_RUB.get("p90", 21_900)),
        "bundle_14_30": int(BASE_PRICES_RUB.get("bundle_14_30", 24_900)),
    }
