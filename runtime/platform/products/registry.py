from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from contracts.product_contract import ProductContract


@dataclass(frozen=True)
class ProductRef:
    product_id: str
    contract: ProductContract


class ProductRegistry:
    """Single source of product contracts (no forks; product = config + modules)."""

    def __init__(self, contracts: Iterable[ProductContract]) -> None:
        self._by_id: dict[str, ProductContract] = {}
        for c in contracts:
            c.validate()
            if c.product_id in self._by_id:
                raise ValueError(f"Duplicate product_id in registry: {c.product_id}")
            self._by_id[c.product_id] = c

    def get(self, product_id: str) -> ProductContract:
        try:
            return self._by_id[product_id]
        except KeyError as e:
            raise KeyError(f"Unknown product_id: {product_id}") from e

    def list_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_id.keys()))
