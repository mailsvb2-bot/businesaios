from __future__ import annotations

from pathlib import Path


def test_yaml_catalog_renders_variants_a_b(tmp_path: Path) -> None:
    # Build a tiny YAML catalog on disk.
    y = tmp_path / "offers.yaml"
    y.write_text(
        """
catalog_id: tcat_v1
schema_version: 1
offers:
  - offer_id: o1
    title: "Test"
    price_rub: 490
    cooldown_days: 0
    variants:
      a:
        text: "AAA"
      b:
        text: "BBB"
""".lstrip(),
        encoding="utf-8",
    )

    from core.offers.yaml_offer_catalog_loader import YamlOfferCatalogLoader
    from core.offers.catalogs.yaml_catalog import YamlOfferCatalogV1

    spec = YamlOfferCatalogLoader(base_dir=tmp_path).load_all()["tcat_v1"]
    cat = YamlOfferCatalogV1.from_spec(spec)

    a = cat.render(offer_id="o1", user_id="u", price_rub=490, variant="a", context={})
    b = cat.render(offer_id="o1", user_id="u", price_rub=490, variant="b", context={})
    assert a.text == "AAA"
    assert b.text == "BBB"


def test_offer_engine_can_choose_both_variants_deterministically(tmp_path: Path) -> None:
    # Build a tiny YAML catalog and register it, then brute-force user_ids until
    # both A and B appear (deterministic, fast).
    (tmp_path / "offers.yaml").write_text(
        """
catalog_id: tcat_v1
schema_version: 1
offers:
  - offer_id: o1
    title: "Test"
    price_rub: 490
    cooldown_days: 0
    variants:
      a:
        text: "AAA"
      b:
        text: "BBB"
""".lstrip(),
        encoding="utf-8",
    )

    from core.offers.yaml_offer_catalog_loader import YamlOfferCatalogLoader
    from core.offers.catalog_registry import OfferCatalogRegistry
    from core.offers.catalogs.yaml_catalog import YamlOfferCatalogV1
    from core.offers.engine import OfferEngine

    spec = YamlOfferCatalogLoader(base_dir=tmp_path).load_all()["tcat_v1"]
    reg = OfferCatalogRegistry(_by_id={"tcat_v1": YamlOfferCatalogV1.from_spec(spec)})
    eng = OfferEngine(catalogs=reg)

    product = {"offer_catalog": {"id": "tcat_v1"}, "modules": {"offers": True}}
    seen = set()
    for i in range(1, 200):
        out = eng.render_offer(product=product, user_id=f"u{i}", offer_id="o1", price_rub=490, step_key="sales:paywall")
        assert out.text in ("AAA", "BBB")
        seen.add(out.text)
        if len(seen) == 2:
            break
    assert seen == {"AAA", "BBB"}
