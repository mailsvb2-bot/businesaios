from __future__ import annotations

from typing import Any, Mapping

from contracts.product_contract import Offer, OfferCatalog


def resolve_offer_catalog(raw: Mapping[str, Any]) -> OfferCatalog:
    """Resolve OfferCatalog from YAML.

    Rules:
    - The catalog is declarative and bounded.
    - No dynamic logic inside YAML.
    """

    oc = raw.get("offer_catalog") if isinstance(raw.get("offer_catalog"), dict) else {}
    cid = str(oc.get("catalog_id") or raw.get("product_id") or "catalog")
    offers_raw = oc.get("offers") if isinstance(oc.get("offers"), list) else []

    offers: list[Offer] = []
    for o in offers_raw:
        if not isinstance(o, dict):
            continue
        offer_id = str(o.get("offer_id") or "").strip()
        if not offer_id:
            continue
        title = str(o.get("title") or offer_id).strip() or offer_id
        try:
            price_minor = int(o.get("price_minor") or 0)
        except (TypeError, ValueError):
            price_minor = 0
        currency = str(o.get("currency") or "RUB").strip() or "RUB"
        period_days = None
        if "period_days" in o and o.get("period_days") is not None:
            try:
                period_days = int(o.get("period_days"))
            except (TypeError, ValueError):
                period_days = None
        tags = o.get("tags")
        tags_t = tuple(str(x) for x in (tags or ()) if str(x)) if isinstance(tags, (list, tuple)) else ()
        metadata = o.get("metadata") if isinstance(o.get("metadata"), dict) else {}

        offers.append(
            Offer(
                offer_id=offer_id,
                title=title,
                price_minor=price_minor,
                currency=currency,
                period_days=period_days,
                tags=tags_t,
                metadata=metadata,
            )
        )

    if not offers:
        # Safe fallback (legacy configs)
        offers = [Offer(offer_id="basic", title="Basic", price_minor=4900_00, currency="RUB")]

    cat = OfferCatalog(catalog_id=cid, offers=tuple(offers))
    cat.validate()
    return cat
