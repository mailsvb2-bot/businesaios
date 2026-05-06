from __future__ import annotations

from pathlib import Path

from core.offers.catalog_resolution import resolve_catalog
from core.offers.catalogs.yaml_catalog_loader import (
    YamlOfferCatalogLoaderV1,
    load_all_yaml_offer_catalog_specs,
    load_yaml_offer_catalog_spec,
)
from core.offers.offer_catalog_resolver import OfferCatalogResolver
from core.offers.yaml_offer_catalog_loader import YamlOfferCatalogLoader


def _write_yaml(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


LEGACY_YAML_TEXT = """\
catalog_id: c1
schema_version: 1
offers:
  - offer_id: o1
    variants:
      a:
        text: hi
"""

CANONICAL_YAML_TEXT = """\
catalog_id: c1
schema_version: 1
offers:
  - offer_id: o1
    base_price_rub: 100
    variants:
      a:
        title: hi
        body: body
"""


def test_legacy_yaml_loader_is_thin_adapter_over_canonical_spec_loader(tmp_path: Path) -> None:
    _write_yaml(tmp_path / "offers.yaml", LEGACY_YAML_TEXT)
    direct = load_yaml_offer_catalog_spec(base_dir=tmp_path, filename="offers.yaml")
    via_compat = YamlOfferCatalogLoader(base_dir=tmp_path).load_file("offers.yaml")
    assert via_compat == direct


def test_legacy_yaml_loader_load_all_delegates_to_canonical_spec_loader(tmp_path: Path) -> None:
    _write_yaml(tmp_path / "offers.yaml", LEGACY_YAML_TEXT)
    assert YamlOfferCatalogLoader(base_dir=tmp_path).load_all() == load_all_yaml_offer_catalog_specs(base_dir=tmp_path)


def test_resolve_catalog_stays_thin_and_delegates_to_offer_catalog_resolver(monkeypatch) -> None:
    calls = []

    def _resolve_from_product(self, *, product, tenant_id, context):
        calls.append((dict(product), tenant_id, context))
        return {"id": "resolved"}

    monkeypatch.setattr(OfferCatalogResolver, "resolve_from_product", _resolve_from_product)
    out = resolve_catalog(catalogs=object(), product={"id": "p1"}, tenant_id="t1", context={"k": "v"})
    assert out == {"id": "resolved"}
    assert calls == [({"id": "p1"}, "t1", {"k": "v"})]


def test_canonical_loader_v1_still_produces_catalog_objects(tmp_path: Path) -> None:
    _write_yaml(tmp_path / "offers.yaml", CANONICAL_YAML_TEXT)
    cat = YamlOfferCatalogLoaderV1(base_dir=tmp_path).load_file("offers.yaml")
    assert getattr(cat, "id", "") == "c1"
