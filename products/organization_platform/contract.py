from __future__ import annotations

from pathlib import Path

from contracts.product_contract import ProductContract
from products.product_loader import ProductLoader

CANON_ORGANIZATION_PLATFORM_COMPAT_FACADE = True


def build_organization_platform_contract() -> ProductContract:
    """Compatibility facade over the canonical manifest/YAML Product source."""

    return ProductLoader(base_dir=Path(__file__).resolve().parents[1]).load("organization_platform.yaml")


__all__ = ["CANON_ORGANIZATION_PLATFORM_COMPAT_FACADE", "build_organization_platform_contract"]
