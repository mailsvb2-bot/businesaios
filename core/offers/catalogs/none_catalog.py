from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.offers.offer_types import OfferCatalog, OfferEligibility, OfferRender


@dataclass(frozen=True)
class NoneOfferCatalogV1(OfferCatalog):
    """Explicitly disables offers for a product.

    Use by setting product.offer_catalog.id = "offer_catalog_none@v1".
    """

    id: str = "offer_catalog_none@v1"

    def list_offers(self) -> list["OfferSummary"]:
        # Empty catalog.
        return []

    def eligible(self, *, user_id: str, entitlements: Mapping[str, Any], context: Mapping[str, Any]) -> OfferEligibility:
        return OfferEligibility(ok=False, reason="disabled")

    def render(
        self,
        *,
        offer_id: str,
        user_id: str,
        price_rub: int,
        variant: str,
        context: Mapping[str, Any],
    ) -> OfferRender:
        # Should never be used for real rendering, but keep it ring-safe.
        return OfferRender(
            offer_id=str(offer_id or ""),
            variant=str(variant or "a"),
            price_rub=int(price_rub or 0),
            text="",
            meta={"disabled": True},
        )
