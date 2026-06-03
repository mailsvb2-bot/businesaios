from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from collections.abc import Mapping

from contracts.product_contract import ProductContract


class ProductRuntimeView(Protocol):
    """Minimal runtime view of the selected product (no dependency on boot internals)."""

    tenant_id: str
    user_id: str
    entrypoint: str
    contract: ProductContract


@dataclass(frozen=True)
class ModuleWiringContext:
    """Shared container for runtime services."""

    services: dict[str, Any]


class RuntimeModule(Protocol):
    module_id: str

    def wire(
        self,
        *,
        product: ProductRuntimeView,
        module_config: Mapping[str, Any],
        ctx: ModuleWiringContext,
    ) -> None: ...
