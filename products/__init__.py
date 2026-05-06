"""Canonical product-definition namespace.

This package intentionally stays separate from ``product``:
- ``products`` = contracts / loaders / catalogs / manifests
- ``product`` = runtime-facing service behavior
"""

from __future__ import annotations

from typing import Tuple

from contracts.product_contract import ProductContract
from products.organization_platform.contract import build_organization_platform_contract

CANON_PRODUCTS_DEFINITION_NAMESPACE = True

def load_all_product_contracts() -> Tuple[ProductContract, ...]:
    """Single import point for all built-in product templates."""

    return (
        build_organization_platform_contract(),
    )

__all__ = [
    'CANON_PRODUCTS_DEFINITION_NAMESPACE',
    'load_all_product_contracts',
]
