from __future__ import annotations

from dataclasses import dataclass

LEGACY_SPECIALIZED_OFFER_CONTRACT = True


@dataclass(frozen=True)
class MarketplaceOffer:
    """Legacy marketplace DTO; canonical sellable definition is contracts.product_contract.ProductOffer."""

    offer_id: str = ''
    category: str = ''
    price_hint: float = 0.0
