from __future__ import annotations

from core.offers.catalog_identity import (
    LEGACY_OFFER_CATALOG_ID,
    NONE_OFFER_CATALOG_ID,
    catalog_registry_key,
    normalize_catalog_id,
    product_catalog_candidates,
)
from core.offers.catalog_registry import OfferCatalogRegistry
from core.offers.offer_catalog_resolver import OfferCatalogResolver


class _Catalog:
    def __init__(self, cid: str) -> None:
        self.id = cid

    def list_offers(self):
        return []

    def eligibility(self, *, offer_id: str, context):
        class _E:
            ok = True
        return _E()

    def render(self, *, offer_id: str, user_id: str, price_rub: int, variant: str, context):
        class _R:
            def __init__(self) -> None:
                self.offer_id = offer_id
                self.variant = variant
                self.price_rub = price_rub
                self.text = offer_id
                self.meta = {}
        return _R()


def test_catalog_identity_constants_are_stable() -> None:
    assert LEGACY_OFFER_CATALOG_ID == "offer_catalog_legacy@v1"
    assert NONE_OFFER_CATALOG_ID == "offer_catalog_none@v1"
    assert normalize_catalog_id("") == LEGACY_OFFER_CATALOG_ID


def test_product_catalog_candidates_are_canonical() -> None:
    assert product_catalog_candidates(tenant_id="tenantA", product_id="p1", environment="stage") == [
        "tenantA:p1:stage",
        "tenantA:p1:prod",
        "default:p1:stage",
        "default:p1:prod",
    ]


def test_catalog_registry_key_requires_real_tenant() -> None:
    missing_tenant_id = ''.join([])
    try:
        catalog_registry_key(tenant_id=missing_tenant_id, product_id="p1", environment="prod")
    except ValueError as exc:
        assert "tenant_id is required" in str(exc)
    else:
        raise AssertionError("empty tenant must be rejected")


def test_resolver_uses_same_catalog_identity_source() -> None:
    registry = OfferCatalogRegistry(_by_id={})
    registry.register(_Catalog(LEGACY_OFFER_CATALOG_ID))
    registry.register(_Catalog("tenantA:p1:prod"))

    out = OfferCatalogResolver(catalogs=registry).resolve_for_product(
        product={"product_id": "p1", "offer_catalog": {"id": LEGACY_OFFER_CATALOG_ID}},
        tenant_id="tenantA",
        context={"environment": "prod"},
    )
    assert getattr(out, "id", None) == "tenantA:p1:prod"
