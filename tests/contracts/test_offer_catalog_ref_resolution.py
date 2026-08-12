from pathlib import Path

import pytest

from products.offer_catalog_resolver import OfferCatalogResolutionError, resolve_offer_catalog
from products.product_loader import ProductLoader


PRODUCTS_DIR = Path(__file__).resolve().parents[2] / "products"


@pytest.mark.parametrize(
    ("filename", "expected_ids", "expected_prices"),
    (
        ("organization_platform.yaml", ("org_launch", "org_scale"), (99_000, 299_000)),
        ("retention.yaml", ("retention_soft",), (60_000,)),
        ("sales.yaml", ("sales_entry",), (60_000,)),
    ),
)
def test_product_loader_materializes_declared_external_offer_catalog(
    filename: str,
    expected_ids: tuple[str, ...],
    expected_prices: tuple[int, ...],
) -> None:
    product = ProductLoader(base_dir=PRODUCTS_DIR).load(filename)

    assert tuple(offer.offer_id for offer in product.offer_catalog.offers) == expected_ids
    assert tuple(offer.price_minor for offer in product.offer_catalog.offers) == expected_prices
    assert all(offer.currency == "RUB" for offer in product.offer_catalog.offers)
    assert all(offer.offer_id != "basic" for offer in product.offer_catalog.offers)


def test_explicit_offer_catalog_ref_is_fail_closed_when_catalog_is_missing(tmp_path: Path) -> None:
    raw = {
        "product_id": "widget",
        "domain": "widget",
        "environment": "prod",
        "offer_catalog_ref": "default:widget:prod",
        "offer_catalog": {
            "offers": [
                {
                    "offer_id": "wrong_fallback",
                    "title": "Must not be used",
                    "price_minor": 1,
                    "currency": "RUB",
                }
            ]
        },
    }

    with pytest.raises(OfferCatalogResolutionError, match="OFFER_CATALOG_NOT_FOUND"):
        resolve_offer_catalog(raw, base_dir=tmp_path)


def test_external_catalog_is_normalized_without_inventing_commercial_rules(tmp_path: Path) -> None:
    catalog_dir = tmp_path / "offer_catalogs"
    catalog_dir.mkdir()
    (catalog_dir / "widget.yaml").write_text(
        """\
catalog_id: offer_catalog_widget@v1
schema_version: 1
offers:
  - offer_id: widget_growth
    base_price_rub: 1990
    rules:
      min_engagement: 0.25
    variants:
      a:
        title: Widget Growth
        body: Existing catalog copy
    meta:
      product: widget
      kind: growth
""",
        encoding="utf-8",
    )
    raw = {
        "product_id": "widget",
        "domain": "widget",
        "environment": "prod",
        "offer_catalog_ref": "default:widget:prod",
    }

    catalog = resolve_offer_catalog(raw, base_dir=tmp_path)

    assert catalog.catalog_id == "offer_catalog_widget@v1"
    assert len(catalog.offers) == 1
    offer = catalog.offers[0]
    assert offer.offer_id == "widget_growth"
    assert offer.title == "Widget Growth"
    assert offer.price_minor == 199_000
    assert offer.currency == "RUB"
    assert offer.period_days is None
    assert offer.metadata["rules"] == {"min_engagement": 0.25}
    assert offer.metadata["variants"]["a"]["body"] == "Existing catalog copy"
    assert offer.metadata["meta"] == {"product": "widget", "kind": "growth"}


def test_external_catalog_ref_cannot_cross_product_boundary(tmp_path: Path) -> None:
    raw = {
        "product_id": "widget",
        "domain": "widget",
        "environment": "prod",
        "offer_catalog_ref": "default:other-product:prod",
    }

    with pytest.raises(OfferCatalogResolutionError, match="OFFER_CATALOG_REF_PRODUCT_MISMATCH"):
        resolve_offer_catalog(raw, base_dir=tmp_path)


def test_legacy_config_without_external_ref_keeps_compatibility_fallback() -> None:
    catalog = resolve_offer_catalog({"product_id": "legacy"})

    assert catalog.catalog_id == "legacy"
    assert len(catalog.offers) == 1
    assert catalog.offers[0].offer_id == "basic"
    assert catalog.offers[0].price_minor == 490_000
