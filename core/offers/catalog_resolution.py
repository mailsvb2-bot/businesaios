from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.offers.catalog_registry import OfferCatalogRegistry
from core.offers.offer_catalog_resolver import OfferCatalogResolver


def resolve_catalog(
    *,
    catalogs: OfferCatalogRegistry,
    product: Mapping[str, Any],
    tenant_id: str | None,
    context: Mapping[str, Any] | None,
):
    """Thin compatibility adapter.

    Canonical offer-catalog lookup logic lives in OfferCatalogResolver.
    This module intentionally keeps only the public compatibility surface used by
    OfferEngine and older call-sites.
    """

    return OfferCatalogResolver(catalogs=catalogs).resolve_from_product(
        product=product,
        tenant_id=tenant_id,
        context=context,
    )
