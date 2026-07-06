from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OfferVariant:
    key: str
    title: str
    body: str


@dataclass(frozen=True)
class OfferRule:
    """Eligibility / cooldown rules (best-effort)."""
    min_engagement: float = 0.0
    max_fatigue: float = 1.0
    cooldown_hours: int = 24


@dataclass(frozen=True)
class OfferSpec:
    offer_id: str
    product_id: str
    variants: Sequence[OfferVariant]
    base_price_rub: int
    rules: OfferRule = OfferRule()
    meta: Mapping[str, Any] = None  # type: ignore[assignment]
