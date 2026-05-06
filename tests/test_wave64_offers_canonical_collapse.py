from __future__ import annotations

from dataclasses import dataclass, field

from core.offers.catalog_registry import OfferCatalogRegistry
from core.offers.catalog_resolution import resolve_catalog
from core.offers.offer_catalog_resolver import OfferCatalogResolver
from core.offers.offer_types import OfferCatalog, OfferEligibility, OfferRender


@dataclass(frozen=True)
class _Catalog(OfferCatalog):
    id: str
    _offers: dict = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_offers", {self.id: {}})

    def list_offers(self):
        return []

    def eligibility(self, *, offer_id: str, context):
        return OfferEligibility(ok=True)

    def render(self, *, offer_id: str, user_id: str, price_rub: int, variant: str, context):
        return OfferRender(offer_id=offer_id, variant=variant, price_rub=price_rub, text=offer_id, meta={})


def test_catalog_resolution_is_thin_shim_over_resolver() -> None:
    registry = OfferCatalogRegistry(_by_id={})
    registry.register(_Catalog(id="offer_catalog_legacy@v1"))
    registry.register(_Catalog(id="tenantA:organization_platform:prod"))

    product = {"product_id": "organization_platform", "offer_catalog": {"id": "offer_catalog_legacy@v1"}}

    via_shim = resolve_catalog(catalogs=registry, product=product, tenant_id="tenantA", context=None)
    via_resolver = OfferCatalogResolver(catalogs=registry).resolve_for_product(
        product=product,
        tenant_id="tenantA",
        context=None,
    )

    assert getattr(via_shim, "id", None) == "tenantA:organization_platform:prod"
    assert getattr(via_resolver, "id", None) == getattr(via_shim, "id", None)


def test_resolver_prefers_catalog_file_override_when_present(tmp_path, monkeypatch) -> None:
    offers_dir = tmp_path / "products" / "offer_catalogs"
    offers_dir.mkdir(parents=True, exist_ok=True)
    (offers_dir / "promo.yaml").write_text(
        "offers:\n  - offer_id: yaml_offer\n    base_price_rub: 10\n    variants:\n      a:\n        title: T\n        body: B\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OFFER_CATALOGS_DIR", str(offers_dir))

    registry = OfferCatalogRegistry(_by_id={})
    registry.register(_Catalog(id="offer_catalog_legacy@v1"))

    product = {
        "product_id": "organization_platform",
        "offer_catalog": {
            "id": "offer_catalog_legacy@v1",
            "params": {"catalog_file": "promo.yaml"},
        },
    }

    cat = OfferCatalogResolver(catalogs=registry).resolve_for_product(product=product, tenant_id=None, context=None)
    raw = getattr(cat, "_offers", {})
    assert "yaml_offer" in raw


def test_resolver_preserves_legacy_fallback_when_product_scope_missing() -> None:
    registry = OfferCatalogRegistry(_by_id={})
    registry.register(_Catalog(id="offer_catalog_legacy@v1"))

    product = {"offer_catalog": {"id": "missing_catalog"}}
    cat = OfferCatalogResolver(catalogs=registry).resolve_for_product(product=product, tenant_id=None, context=None)
    assert getattr(cat, "id", None) == "offer_catalog_legacy@v1"
