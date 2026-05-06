from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from core.behavior.operator_catalogs.registry import OperatorCatalogRegistry


@lru_cache(maxsize=1)
def default_operator_catalog_registry() -> OperatorCatalogRegistry:
    # products/operator_catalogs lives at repo_root/products/operator_catalogs
    repo_root = Path(__file__).resolve().parents[3]
    base_dir = repo_root / "products" / "operator_catalogs"
    return OperatorCatalogRegistry(base_dir=base_dir)
