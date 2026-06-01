from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True


from dataclasses import dataclass
from typing import Any

from runtime.boot.product_system_builder import SystemBuilder
from runtime.platform.config.env_flags import env_bool, env_str
from runtime.tenancy import normalize_tenant_id


@dataclass(frozen=True)
class ProductPreflightResult:
    system: Any | None
    blocked: bool


def run_product_preflight(*, tenant_id: str) -> ProductPreflightResult:
    """Run optional product-contract preflight.

    This function is intentionally side-effect free except for constructing the
    product-contract system. If preflight is disabled or incomplete, it returns
    a non-blocking result.
    """
    if not env_bool("PRODUCT_BOOT_ENABLE"):
        return ProductPreflightResult(system=None, blocked=False)

    user_id = env_str("PRODUCT_BOOT_USER_ID").strip()
    if not user_id:
        return ProductPreflightResult(system=None, blocked=False)

    effective_tenant_id = normalize_tenant_id(tenant_id)
    if not effective_tenant_id:
        return ProductPreflightResult(system=None, blocked=False)

    entrypoint = env_str("PRODUCT_BOOT_ENTRYPOINT", "telegram").strip() or "telegram"
    product_id = env_str("PRODUCT_BOOT_PRODUCT_ID").strip()
    hints: dict[str, str] = {"product_id": product_id} if product_id else {}

    builder = SystemBuilder(default_product_id="organization_platform")
    system = builder.build(tenant_id=effective_tenant_id, user_id=user_id, entrypoint=entrypoint, hints=hints)
    blocked = not bool(getattr(getattr(system, "access", None), "allowed", False))
    return ProductPreflightResult(system=system, blocked=blocked)
