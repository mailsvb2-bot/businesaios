from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True


from dataclasses import dataclass
from collections.abc import Mapping

from bootstrap.product_boot import BootProductContext, ProductBoot
from contracts.product_contract import ProductContract
from products import load_all_product_contracts
from runtime.platform.products.registry import ProductRegistry


@dataclass(frozen=True)
class RuntimeRequest:
    tenant_id: str
    user_id: str
    entrypoint: str
    hints: Mapping[str, str]


class SystemBuilderProducts:
    """Product-aware boot shim.

    Selects + validates product contract deterministically.
    """

    def __init__(self, *, default_product_id: str = "organization_platform") -> None:
        registry = ProductRegistry(load_all_product_contracts())
        self._boot = ProductBoot(registry=registry, default_product_id=default_product_id)

    def boot_product(self, req: RuntimeRequest) -> BootProductContext:
        return self._boot.build(
            tenant_id=req.tenant_id,
            user_id=req.user_id,
            entrypoint=req.entrypoint,
            hints=req.hints,
        )
