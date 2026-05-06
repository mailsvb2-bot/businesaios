from __future__ import annotations

from pathlib import Path

from core.offers.offer_catalog_resolver import OfferCatalogKey, OfferCatalogResolver


def _write_yaml(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_offer_catalog_resolver_falls_back_to_default(tmp_path, monkeypatch):
    # Prepare minimal structure:
    #   data/offer_catalogs/default/organization_platform/prod.yaml
    data_dir = tmp_path / "data" / "offer_catalogs"
    _write_yaml(
        data_dir / "default" / "organization_platform" / "prod.yaml",
        "offers:\n  - offer_id: test_offer\n    base_price_rub: 123\n    variants:\n      a:\n        title: 'T'\n        body: 'B'\n",
    )

    monkeypatch.setenv("OFFER_CATALOGS_DATA_DIR", str(data_dir))

    resolver = OfferCatalogResolver()
    cat = resolver.resolve(key=OfferCatalogKey(tenant_id="tenantX", product_id="organization_platform", environment="prod"))
    raw = getattr(cat, "_offers", {})
    assert isinstance(raw, dict)
    assert "test_offer" in raw


def test_offer_catalog_resolver_prefers_tenant_specific(tmp_path, monkeypatch):
    data_dir = tmp_path / "data" / "offer_catalogs"
    _write_yaml(
        data_dir / "default" / "organization_platform" / "prod.yaml",
        "offers:\n  - offer_id: default_offer\n    base_price_rub: 1\n    variants:\n      a:\n        title: 'D'\n        body: 'D'\n",
    )
    _write_yaml(
        data_dir / "tenantA" / "organization_platform" / "prod.yaml",
        "offers:\n  - offer_id: tenant_offer\n    base_price_rub: 2\n    variants:\n      a:\n        title: 'T'\n        body: 'T'\n",
    )

    monkeypatch.setenv("OFFER_CATALOGS_DATA_DIR", str(data_dir))

    resolver = OfferCatalogResolver()
    cat = resolver.resolve(key=OfferCatalogKey(tenant_id="tenantA", product_id="organization_platform", environment="prod"))
    raw = getattr(cat, "_offers", {})
    assert "tenant_offer" in raw
    assert "default_offer" not in raw
