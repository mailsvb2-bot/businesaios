"""Compatibility namespace for historical ``core.products.*`` imports.

Canonical planning logic lives under ``core.product``.
Canonical DTO contract lives under ``contracts.product_contract``.
This package intentionally exposes only compatibility helpers and aliases.
"""

from __future__ import annotations

import sys
from importlib import import_module
from typing import Any

from contracts.product_contract import (
    EntitlementsSpec,
    EntryPolicy,
    ModuleSpec,
    ModulesSpec,
    Offer,
    OfferCatalog,
    PricingModel,
    ProductContract,
    TelemetryEventSpec,
    TelemetryField,
    TelemetrySchema,
)
from core.offers.offer_catalog_resolver import OfferCatalogKey, OfferCatalogResolver
from core.offers.offer_types import OfferCatalog as RuntimeOfferCatalog
from core.tenancy.normalization import require_tenant_id

NON_CANON_COMPAT_NAMESPACE = True
CANON_TRANSITION_SURFACE = True
CANON_COMPAT_SHIM = True

def resolve_offer_catalog_for_product(*, product: ProductContract, tenant_id: str) -> RuntimeOfferCatalog:
    """Backward-compat helper for call-sites that still resolve catalogs by product."""

    resolver = OfferCatalogResolver()
    key = OfferCatalogKey(
        tenant_id=require_tenant_id(tenant_id),
        product_id=str(product.product_id),
        environment=str(getattr(product, "environment", "prod") or "prod"),
    )
    return resolver.resolve(key=key)


def product_contract_as_mapping(product: ProductContract) -> dict[str, Any]:
    """Small helper to keep older mapping-based APIs working."""

    return dict(product.as_dict())

__all__ = [
    "CANON_TRANSITION_SURFACE",
    "NON_CANON_COMPAT_NAMESPACE",
    "CANON_COMPAT_SHIM",
    "resolve_offer_catalog_for_product",
    "product_contract_as_mapping",
    "EntryPolicy",
    "Offer",
    "OfferCatalog",
    "PricingModel",
    "TelemetryField",
    "TelemetryEventSpec",
    "TelemetrySchema",
    "EntitlementsSpec",
    "ModuleSpec",
    "ModulesSpec",
    "ProductContract",
]


_COMPAT_ALIAS_MAP = {
    "product_contract": "contracts.product_contract",
}


def _install_product_aliases() -> None:
    package = sys.modules[__name__]
    for alias_name, target_module_name in _COMPAT_ALIAS_MAP.items():
        target_module = import_module(target_module_name)
        qualified_name = f"{__name__}.{alias_name}"
        sys.modules[qualified_name] = target_module
        setattr(package, alias_name, target_module)


_install_product_aliases()
