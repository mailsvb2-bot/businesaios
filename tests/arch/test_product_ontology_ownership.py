from __future__ import annotations

import ast
from pathlib import Path

from canon.business_ontology_inventory import OwnershipAuditStatus, ontology_ownership_by_entity
from products import load_all_product_contracts
from products.product_catalog import CANON_PRODUCT_CATALOG_OWNER
from runtime.platform.config.yaml_loader import load_yaml
from runtime.platform.products.validator import ProductContractValidator

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("application", "bootstrap", "contracts", "core", "products", "runtime", "storage")


def _production_python_files():
    for root_name in PRODUCTION_ROOTS:
        root = ROOT / root_name
        if root.exists():
            yield from root.rglob("*.py")


def test_product_inventory_declares_single_catalog_owner() -> None:
    row = ontology_ownership_by_entity()["Product"]
    assert CANON_PRODUCT_CATALOG_OWNER is True
    assert row.status is OwnershipAuditStatus.DONE
    assert row.authoritative_module == "contracts.product_contract"
    assert row.storage_owner == "products.product_catalog"
    assert row.allowed_writers == ("products.product_loader",)
    assert row.allowed_readers == ("products.product_resolver", "runtime.boot.system_builder_products")


def test_product_contract_constructor_has_one_production_owner() -> None:
    owners: list[Path] = []
    for path in _production_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ProductContract":
                owners.append(path.relative_to(ROOT))
    assert owners == [Path("products/product_loader.py")]


def test_manifest_is_index_only_and_all_builtin_products_validate() -> None:
    raw = load_yaml(ROOT / "products/manifest.yaml")
    assert raw.get("schema") == "products_manifest@v1"
    packages = raw.get("packages")
    assert isinstance(packages, list) and packages
    assert all(set(row) == {"config"} for row in packages)
    contracts = load_all_product_contracts()
    assert tuple(item.product_id for item in contracts) == ("organization_platform", "salesbot", "retentionbot")
    validator = ProductContractValidator()
    assert all(validator.validate(item) == () for item in contracts)


def test_organization_compat_facade_contains_no_product_semantics() -> None:
    source = (ROOT / "products/organization_platform/contract.py").read_text(encoding="utf-8")
    for forbidden in ("ProductContract(", "EntryPolicy(", "OfferCatalog(", "TelemetrySchema(", "PricingV1"):
        assert forbidden not in source
    assert "ProductLoader" in source


def test_builtin_pricing_models_do_not_duplicate_offer_prices() -> None:
    for name in ("organization_platform.yaml", "sales.yaml", "retention.yaml"):
        raw = load_yaml(ROOT / "products" / name)
        pricing = raw.get("pricing_model")
        assert isinstance(pricing, dict)
        text = repr(pricing).casefold()
        assert "price" not in text
        assert "amount" not in text
