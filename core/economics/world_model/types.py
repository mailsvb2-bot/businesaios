from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from collections.abc import Mapping


@dataclass(frozen=True)
class MarketContext:
    """Lightweight contextual signals used for conditioning demand/conv.

    Keep it small: this is used in hot paths.
    """

    tenant_id: str
    product_id: str
    currency: str = "USD"

    # Optional high-level segments (stringly typed, controlled upstream).
    channel: str | None = None   # e.g. "tg", "web", "ads"
    geo: str | None = None       # e.g. "NL", "DE"
    device: str | None = None    # e.g. "mobile", "desktop"
    dow: int | None = None       # day-of-week 0..6 (Mon=0)
    hour: int | None = None      # 0..23


@dataclass(frozen=True)
class PricePoint:
    amount: float
    # Optional: allow multiple currencies by normalizing upstream.
    currency: str = "USD"


@dataclass(frozen=True)
class DemandObservation:
    """Observed demand at a price point (aggregated)."""

    context: MarketContext
    price: PricePoint
    # units sold / purchases count for the window
    units: float
    # exposure (impressions/visits) that generated demand; optional
    exposure: float | None = None
    # time window size in seconds for comparability (optional)
    window_s: float | None = None


@dataclass(frozen=True)
class ConversionObservation:
    """Observed conversion probability at a price point (aggregated)."""

    context: MarketContext
    price: PricePoint
    # conversions / numerator
    conversions: float
    # opportunities / denominator
    opportunities: float


class FunnelStage(str, Enum):
    VISIT = "visit"
    ADD_TO_CART = "add_to_cart"
    CHECKOUT = "checkout"
    PURCHASE = "purchase"


@dataclass(frozen=True)
class FunnelObservation:
    """Aggregated funnel counts for a window, optionally per price point."""

    context: MarketContext
    price: PricePoint | None
    # stage -> count
    counts: Mapping[FunnelStage, float]
