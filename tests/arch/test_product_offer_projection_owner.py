from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_product_offer_projection_uses_canonical_yaml_loader() -> None:
    text = (ROOT / "products" / "offer_catalog_resolver.py").read_text(encoding="utf-8")
    assert "from core.offers.catalogs.yaml_catalog_loader import load_yaml_offer_catalog_spec" in text
    assert "import yaml" not in text
    assert "yaml.safe_load" not in text
    assert "CANON_PRODUCT_OFFER_PROJECTION = True" in text


def test_product_offer_projection_does_not_own_live_catalog_mutations() -> None:
    text = (ROOT / "products" / "offer_catalog_resolver.py").read_text(encoding="utf-8")
    for forbidden in ("write_text(", ".replace(", "atomic_write", "OFFER_CATALOGS_DATA_DIR"):
        assert forbidden not in text
