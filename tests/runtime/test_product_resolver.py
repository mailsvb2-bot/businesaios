from __future__ import annotations

from pathlib import Path

from products.product_resolver import ProductResolver


def test_product_resolver_start_token_sales() -> None:
    r = ProductResolver(base_dir=Path(__file__).resolve().parents[2] / "products", default_config="organization_platform.yaml")
    ctx = r.resolve(command="/start", args="sales", user_settings={})
    assert isinstance(ctx, dict)
    assert ctx.get("domain") == "sales"


def test_product_resolver_user_settings_domain() -> None:
    r = ProductResolver(base_dir=Path(__file__).resolve().parents[2] / "products", default_config="organization_platform.yaml")
    ctx = r.resolve(command=None, args="", user_settings={"product_domain": "retention"})
    assert ctx.get("domain") == "retention"
