from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MarketplaceOffer:
    offer_id: str = ''
    category: str = ''
    price_hint: float = 0.0
