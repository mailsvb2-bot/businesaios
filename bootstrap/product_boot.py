from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

from dataclasses import dataclass
from importlib import import_module
from typing import Any
from collections.abc import Mapping

from bootstrap.route_surface import attach_route_surface
from contracts.product_contract import ProductContract
from runtime.platform.products.registry import ProductRegistry


def _load_handler(module_name: str, attr_name: str) -> Any:
    module = import_module(module_name)
    return getattr(module, attr_name)


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


def _product_handlers() -> dict[str, Any]:
    return {
        "product_build": _load_handler("runtime.handlers.product_build", "handle_product_build"),
        "product_explain": _load_handler("runtime.handlers.product_explain", "handle_product_explain"),
    }


def register_product_routes(app: object) -> object:
    return attach_route_surface(
        app,
        domain="product",
        handlers=_product_handlers(),
        services={
            "boot_context_cls": BootProductContext,
            "boot_cls": ProductBoot,
            "surface_status": "wired",
        },
    )
