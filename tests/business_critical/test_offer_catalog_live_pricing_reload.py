from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from config.yaml_loader_shared import load_yaml
from core.offers.catalog_registry import OfferCatalogRegistry
from core.offers.catalogs.yaml_catalog import YamlOfferCatalogV1
from runtime._internal.effects_domains.admin_pricing import prepare_offer_price_update


def _write_catalog(path: Path, *, price: int, version: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "catalog_id": "business-a:crm-pro:test",
                "pricing_version": version,
                "offers": [
                    {
                        "offer_id": "crm-pro-monthly",
                        "base_price_rub": int(price),
                        "rules": {},
                        "variants": {
                            "a": {
                                "title": "CRM Pro",
                                "body": "Business CRM plan",
                            }
                        },
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _factory(path: Path):
    def build() -> YamlOfferCatalogV1:
        return YamlOfferCatalogV1.from_spec(
            load_yaml(path, allow_empty=False, cache=False)
        )

    return build


@pytest.mark.lock
def test_live_registry_reloads_changed_canonical_catalog_without_restart(tmp_path: Path) -> None:
    path = tmp_path / "business-a" / "crm-pro" / "test.yaml"
    _write_catalog(path, price=100, version="version-old")

    registry = OfferCatalogRegistry(_by_id={})
    registry.register_yaml_factory(
        "business-a:crm-pro:test",
        path=path,
        factory=_factory(path),
    )

    first = registry.get("business-a:crm-pro:test")
    assert first.list_offers()[0].base_price_rub == 100

    transaction = prepare_offer_price_update(
        tenant_id="business-a",
        product_id="crm-pro",
        environment="test",
        offer_id="crm-pro-monthly",
        new_price=900,
        pricing_version="version-new-with-different-size",
        catalog_path=path,
    )
    try:
        transaction.apply()
        os.utime(path, None)
    finally:
        transaction.finalize()

    second = registry.get("business-a:crm-pro:test")

    assert second is not first
    assert second.list_offers()[0].base_price_rub == 900
    assert load_yaml(path, allow_empty=False, cache=False)["pricing_version"] == "version-new-with-different-size"
