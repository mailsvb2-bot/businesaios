from __future__ import annotations

from core.observability.structured_logging import log_exception_throttled
from core.offers.offer_catalog_resolver import OfferCatalogKey, OfferCatalogResolver
from core.tenancy.normalization import normalize_tenant_id_or_unknown


def resolve_offer_choices(ctx, *, default_price_rub: int) -> list[tuple[str, str, int]]:
    try:
        prod = dict(getattr(ctx.state, "product", {}) or {})
        product_id = str(prod.get("product_id") or prod.get("product") or "organization_platform")
        env = str(prod.get("environment") or "prod")
        tenant_id = normalize_tenant_id_or_unknown(getattr(ctx.state, "tenant_id", None))
        resolver = OfferCatalogResolver()
        cat = resolver.resolve(key=OfferCatalogKey(tenant_id=tenant_id, product_id=product_id, environment=env))
        offers = []
        for o in (cat.list_offers() or []):
            try:
                offers.append((str(o.offer_id), str(o.title)[:32], int(o.base_price_rub or default_price_rub)))
            except Exception:
                continue
        if offers:
            return offers
    except Exception as exc:
        log_exception_throttled(__name__, "autopilot_offer_catalog_resolve_failed", exc)
    return [("default", "Полный доступ", int(default_price_rub))]
