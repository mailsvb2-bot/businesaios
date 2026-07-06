from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from runtime.platform.products.registry import ProductRegistry


@dataclass(frozen=True)
class ProductSelection:
    product_id: str
    domain: str
    entrypoint: str


class ProductSelector:
    """Deterministic selection of product_id based on entrypoint and request hints."""

    def __init__(self, registry: ProductRegistry) -> None:
        self._registry = registry

    def resolve_product(self, *, default_product_id: str, entrypoint: str, hints: Mapping[str, str]) -> ProductSelection:
        product_id = hints.get("product_id") or default_product_id
        c = self._registry.get(product_id)
        if entrypoint not in c.entry_policy.entrypoints:
            raise ValueError(f"Entrypoint '{entrypoint}' not allowed for product '{product_id}'")
        return ProductSelection(product_id=product_id, domain=c.domain, entrypoint=entrypoint)

    select = resolve_product
