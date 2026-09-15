from __future__ import annotations

from pathlib import Path

from contracts.product_contract import ProductContract
from products.product_loader import ProductLoader
from runtime.platform.config.yaml_loader import load_yaml

CANON_PRODUCT_CATALOG_OWNER = True
_MANIFEST_SCHEMA = "products_manifest@v1"


def load_builtin_product_contracts(*, base_dir: Path | None = None) -> tuple[ProductContract, ...]:
    root = (base_dir or Path(__file__).parent).resolve()
    raw = load_yaml(root / "manifest.yaml")
    if str(raw.get("schema") or "").strip() != _MANIFEST_SCHEMA:
        raise ValueError("BAD_PRODUCTS_MANIFEST_SCHEMA")
    packages = raw.get("packages")
    if not isinstance(packages, list) or not packages:
        raise ValueError("BAD_PRODUCTS_MANIFEST_PACKAGES")
    loader = ProductLoader(base_dir=root)
    contracts: list[ProductContract] = []
    seen_configs: set[str] = set()
    seen_products: set[str] = set()
    for row in packages:
        if not isinstance(row, dict):
            raise ValueError("BAD_PRODUCTS_MANIFEST_ENTRY")
        config = str(row.get("config") or "").strip()
        if not config or config in seen_configs:
            raise ValueError("BAD_PRODUCTS_MANIFEST_CONFIG")
        contract = loader.load(config)
        if contract.product_id in seen_products:
            raise ValueError(f"DUPLICATE_PRODUCT_ID:{contract.product_id}")
        seen_configs.add(config)
        seen_products.add(contract.product_id)
        contracts.append(contract)
    return tuple(contracts)


__all__ = ["CANON_PRODUCT_CATALOG_OWNER", "load_builtin_product_contracts"]
