from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from core.observability.silent import swallow
from core.offers.offer_types import OfferCatalog, OfferEligibility, OfferRender, OfferSummary

CATALOG_ID: str = "retention_legacy"


@dataclass(frozen=True)
class Offer:
    arm: str
    title: str
    base_price_rub: int
    entitlements: list[tuple[str, int]]


# Stable retention offer IDs preserved for existing pricing flows.
OFFERS: dict[str, Offer] = {
    "offer_30": Offer(
        arm="offer_30",
        title="30 дней",
        base_price_rub=14_900,
        entitlements=[("program30", 30)],
    ),
    "offer_90": Offer(
        arm="offer_90",
        title="90 дней",
        base_price_rub=21_900,
        entitlements=[("program90", 90)],
    ),
    "bundle_14_30": Offer(
        arm="bundle_14_30",
        title="Бандл 14 + 30",
        base_price_rub=24_900,
        entitlements=[("course14", 14), ("program30", 30)],
    ),
}


def build_catalog() -> dict[str, Offer]:
    return dict(OFFERS)


@dataclass(frozen=True)
class LegacyOfferCatalogV1(OfferCatalog):
    """Retention catalog backed by the preserved offer data."""

    id: str = "offer_catalog_legacy@v1"

    def list_offers(self) -> list[OfferSummary]:
        out: list[OfferSummary] = []
        for oid in sorted(OFFERS.keys()):
            offer = OFFERS.get(oid)
            title = offer.title if offer else str(oid)
            base_price_rub = int(offer.base_price_rub) if offer else 0
            out.append(OfferSummary(offer_id=str(oid), title=str(title), base_price_rub=base_price_rub))
        return out

    def eligible(self, *, user_id: str, entitlements: Mapping[str, Any], context: Mapping[str, Any]) -> OfferEligibility:
        try:
            if bool((entitlements or {}).get("full_access")):
                return OfferEligibility(ok=False, reason="already_full_access")
        except Exception:
            swallow(__name__, "core/offers/catalogs/retention_catalog.py")
        return OfferEligibility(ok=True, reason="ok")

    def render(self, *, offer_id: str, user_id: str, price_rub: int, variant: str, context: Mapping[str, Any]) -> OfferRender:
        oid = str(offer_id)
        offer = OFFERS.get(oid)
        title = offer.title if offer else oid
        if variant == "b":
            text = f"✨ {title}: доступ за {int(price_rub)} ₽\nЕсли сейчас не вовремя — можно начать позже."
        else:
            text = f"💡 Предложение: {title} за {int(price_rub)} ₽"
        return OfferRender(
            offer_id=oid,
            variant=str(variant or "a"),
            price_rub=int(price_rub),
            text=text,
            meta={"catalog": self.id, "title": title},
        )


__all__ = [
    "CATALOG_ID",
    "OFFERS",
    "Offer",
    "LegacyOfferCatalogV1",
    "build_catalog",
]
