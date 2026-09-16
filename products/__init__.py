"""Canonical product-definition namespace."""

from __future__ import annotations

from contracts.product_contract import ProductContract
from products.product_catalog import load_builtin_product_contracts

CANON_PRODUCTS_DEFINITION_NAMESPACE = True


def load_all_product_contracts() -> tuple[ProductContract, ...]:
    """Load every built-in product through the single manifest/YAML owner."""

    return load_builtin_product_contracts()


__all__ = ["CANON_PRODUCTS_DEFINITION_NAMESPACE", "load_all_product_contracts"]
