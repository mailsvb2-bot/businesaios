from __future__ import annotations

from pathlib import Path

from runtime._internal.offer_catalog_mutation import (
    canonical_catalog_path,
    resolve_catalog_read_path,
)
from runtime.tenancy import require_tenant_id


def business_catalog_paths(
    *,
    tenant_id: str,
    business_id: str,
    product: str,
    env: str,
) -> tuple[Path, Path]:
    tenant = require_tenant_id(tenant_id)
    business = str(business_id or "").strip()
    if not business:
        raise RuntimeError("BUSINESS_ID_REQUIRED")
    prod = str(product).strip() or "organization_platform"
    envv = str(env).strip() or "prod"
    business_path = canonical_catalog_path(
        tenant_id=tenant,
        business_id=business,
        product_id=prod,
        environment=envv,
    )
    legacy_path = canonical_catalog_path(
        tenant_id=tenant,
        product_id=prod,
        environment=envv,
    )
    return business_path, legacy_path


def resolve_catalog_paths(
    *,
    tenant_id: str,
    business_id: str,
    product: str,
    env: str,
) -> tuple[Path, Path, Path]:
    business_path, legacy_path = business_catalog_paths(
        tenant_id=tenant_id,
        business_id=business_id,
        product=product,
        env=env,
    )
    read_path = resolve_catalog_read_path(
        business_catalog_path=business_path,
        legacy_catalog_path=legacy_path,
    )
    return read_path, business_path, legacy_path


def append_line(text: str, line: str) -> str:
    text = (text or "").rstrip()
    if not text:
        return str(line)
    return text + "\n" + str(line)
