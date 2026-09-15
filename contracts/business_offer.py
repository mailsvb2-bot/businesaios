from __future__ import annotations

from dataclasses import dataclass

LEGACY_SPECIALIZED_OFFER_CONTRACT = True


@dataclass(frozen=True)
class BusinessOffer:
    """Legacy specialized DTO; canonical sellable definition is contracts.product_contract.ProductOffer."""

    offer_id: str = ''
    headline: str = ''
    price_hint: float = 0.0
