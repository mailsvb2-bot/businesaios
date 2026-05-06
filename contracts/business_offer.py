from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BusinessOffer:
    offer_id: str = ''
    headline: str = ''
    price_hint: float = 0.0
