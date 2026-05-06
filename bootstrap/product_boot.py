from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

from dataclasses import dataclass
from typing import Mapping

from contracts.product_contract import ProductContract
from runtime.platform.products.registry import ProductRegistry
from bootstrap.route_surface import attach_route_surface
from runtime.handlers.product_build import handle_product_build
from runtime.handlers.product_explain import handle_product_explain


@dataclass(frozen=True)
class BootProductContext:
    tenant_id: str
    user_id: str
    entrypoint: str
    product_id: str
    contract: ProductContract
    hints: Mapping[str, str]


class ProductBoot:
    """Tiny canonical product selector for boot wiring.

    Keeps product choice declarative and prevents ad-hoc product selection
    branches from appearing elsewhere in runtime boot.
    """

    def __init__(self, *, registry: ProductRegistry, default_product_id: str) -> None:
        self._registry = registry
        self._default_product_id = str(default_product_id)

    def build(
        self,
        *,
        tenant_id: str,
        user_id: str,
        entrypoint: str,
        hints: Mapping[str, str],
    ) -> BootProductContext:
        product_id = str(hints.get("product_id") or self._default_product_id)
        contract = self._registry.get(product_id)
        return BootProductContext(
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            entrypoint=str(entrypoint),
            product_id=product_id,
            contract=contract,
            hints=dict(hints),
        )


def register_product_routes(app: object) -> object:
    handlers = {
        "product_build": handle_product_build,
        "product_explain": handle_product_explain,
    }
    return attach_route_surface(
        app,
        domain="product",
        handlers=handlers,
        services={
            "boot_context_cls": BootProductContext,
            "boot_cls": ProductBoot,
            "surface_status": "wired",
        },
    )
