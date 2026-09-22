"""Canonical offer-catalog identity helpers.

This module is intentionally tiny: it holds the *one* source of truth for
catalog ids and tenant/product/env registry candidate building.

Meaningful offers logic stays in OfferCatalogResolver and OfferCatalogRegistry.
This helper exists only to prevent duplicated string-shape logic from drifting.
"""

from __future__ import annotations

from core.tenancy.normalization import normalize_tenant_id

LEGACY_OFFER_CATALOG_ID: str = "offer_catalog_legacy@v1"
NONE_OFFER_CATALOG_ID: str = "offer_catalog_none@v1"


def normalize_catalog_id(catalog_id: str | None) -> str:
    return str(catalog_id or "").strip() or LEGACY_OFFER_CATALOG_ID


def catalog_registry_key(
    *,
    tenant_id: str | None,
    product_id: str,
    environment: str | None = "prod",
    business_id: str | None = None,
) -> str:
    tenant = normalize_tenant_id(tenant_id)
    business = str(business_id or "").strip()
    product = str(product_id or "").strip()
    env = str(environment or "prod").strip() or "prod"
    if not tenant:
        raise ValueError("tenant_id is required")
    if not product:
        raise ValueError("product_id is required")
    if business:
        return f"{tenant}:{business}:{product}:{env}"
    return f"{tenant}:{product}:{env}"


def product_catalog_candidates(
    *,
    tenant_id: str | None,
    product_id: str,
    environment: str | None = "prod",
    business_id: str | None = None,
) -> list[str]:
    product = str(product_id or "").strip()
    env = str(environment or "prod").strip() or "prod"
    if not product:
        raise ValueError("product_id is required")

    tenant = normalize_tenant_id(tenant_id)
    business = str(business_id or "").strip()
    candidates: list[str] = []
    if tenant and business:
        candidates.extend([
            catalog_registry_key(
                tenant_id=tenant,
                business_id=business,
                product_id=product,
                environment=env,
            ),
            catalog_registry_key(
                tenant_id=tenant,
                business_id=business,
                product_id=product,
                environment="prod",
            ),
        ])
    if tenant:
        candidates.extend([
            catalog_registry_key(tenant_id=tenant, product_id=product, environment=env),
            catalog_registry_key(tenant_id=tenant, product_id=product, environment="prod"),
        ])
    candidates.extend([
        f"default:{product}:{env}",
        f"default:{product}:prod",
    ])
    return list(dict.fromkeys(candidates))
