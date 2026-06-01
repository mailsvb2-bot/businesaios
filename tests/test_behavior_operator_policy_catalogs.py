from __future__ import annotations

from pathlib import Path

import pytest

from core.behavior.operator_policy_catalogs import (
    OperatorPolicyCatalogResolver,
    OperatorPolicyContext,
    load_operator_policy_catalog,
)


def test_policy_loader_and_basic_rules(tmp_path: Path) -> None:
    p = tmp_path / "p.yaml"
    p.write_text(
        """name: x
version: 1
defaults:
  allow: ["*"]
stages:
  discovery:
    deny: ["price_hard_push"]
""",
        encoding="utf-8",
    )
    cat = load_operator_policy_catalog(p, name="x")
    assert cat.is_allowed("content_nudge", ctx=OperatorPolicyContext(funnel_stage="discovery")) is True
    assert cat.is_allowed("price_hard_push", ctx=OperatorPolicyContext(funnel_stage="discovery")) is False


def test_policy_resolver_fallback_chain_uses_default(tmp_path: Path, monkeypatch) -> None:
    # Build a fake products/operator_policy_catalogs tree in tmp
    root = tmp_path / "products" / "operator_policy_catalogs"
    root.mkdir(parents=True)
    (root / "default.yaml").write_text(
        """name: default
version: 1
defaults:
  allow: ["*"]
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    res = OperatorPolicyCatalogResolver(root_dir=str(root))
    cat = res.resolve(catalog_ref=None, tenant_id=None, product_id=None, env="prod")
    assert cat.name == "default"


def test_policy_validation_rejects_unknown_operator_keys(tmp_path: Path) -> None:
    p = tmp_path / "p.yaml"
    p.write_text(
        """name: x
version: 1
defaults:
  allow: ["*"]
stages:
  discovery:
    deny: ["unknown_key_zzz"]
""",
        encoding="utf-8",
    )
    cat = load_operator_policy_catalog(p, name="x")
    with pytest.raises(ValueError):
        cat.validate_operator_keys(["content_nudge", "price_hard_push"])
