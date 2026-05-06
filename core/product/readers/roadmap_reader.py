from __future__ import annotations

from core.product.types import RoadmapCapacity


class InMemoryRoadmapReader:
    def __init__(self, capacities_by_product: dict[str, RoadmapCapacity] | None = None) -> None:
        self._capacities_by_product = capacities_by_product or {}

    def read_capacity(self, product_id: str) -> RoadmapCapacity:
        return self._capacities_by_product.get(
            product_id,
            RoadmapCapacity(max_now_items=3, max_next_items=5, max_later_items=10),
        )
