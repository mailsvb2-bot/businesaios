from __future__ import annotations

"""Types for the product-contract system builder."""

from dataclasses import dataclass
from typing import Any

from runtime.platform.identity.enforcement import EnforcedProductAccess
from runtime.modules.module_protocol import ProductRuntimeView


@dataclass
class ProductContractSystem:
    services: dict[str, Any]
    product_id: str
    domain: str
    access: EnforcedProductAccess


@dataclass(frozen=True)
class RuntimeView(ProductRuntimeView):
    tenant_id: str
    user_id: str
    entrypoint: str
    contract: Any


__all__ = ["ProductContractSystem", "RuntimeView"]
