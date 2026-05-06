from __future__ import annotations

import os


def test_offer_catalogs_yaml_strict_loads():
    # Fail fast on malformed YAML catalogs.
    os.environ["OFFER_CATALOGS_STRICT"] = "1"

    from core.offers.catalog_registry import default_offer_catalog_registry

    reg = default_offer_catalog_registry()

    # Must have built-ins.
    assert reg.get("offer_catalog_legacy@v1") is not None
    assert reg.get("offer_catalog_none@v1") is not None

    # Ensure tenant/product/env catalogs can be instantiated in strict mode.
    # (If data/offer_catalogs is missing, this loop is harmless.)
    for cid in list(getattr(reg, "_by_id", {}).keys()):
        _ = reg.get(cid)
