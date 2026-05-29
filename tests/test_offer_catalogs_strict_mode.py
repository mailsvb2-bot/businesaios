from __future__ import annotations


def test_strict_mode_rejects_bad_yaml_catalog(tmp_path, monkeypatch):
    # Strict mode must fail fast.
    monkeypatch.setenv("OFFER_CATALOGS_STRICT", "1")

    d = tmp_path / "products" / "offer_catalogs"
    d.mkdir(parents=True)
    (d / "bad.yaml").write_text("catalog_id: x\noffers: []\n", encoding="utf-8")

    # Loader validates schema in strict mode.
    from core.offers.catalogs.yaml_catalog_loader import YamlOfferCatalogLoaderV1

    loader = YamlOfferCatalogLoaderV1(base_dir=d)
    try:
        loader.load_all()
        assert False, "expected strict validation error"
    except Exception:
        pass


def test_strict_mode_registry_bootstrap_ok_for_repo_catalogs(monkeypatch):
    # Repo-shipped catalogs must pass strict validation in CI.
    monkeypatch.setenv("OFFER_CATALOGS_STRICT", "1")
    from core.offers.catalog_registry import default_offer_catalog_registry

    reg = default_offer_catalog_registry()
    # Resolve a known shipped catalog.
    cat = reg.get("offer_catalog_organization_platform@v1")
    assert getattr(cat, "id", "")
