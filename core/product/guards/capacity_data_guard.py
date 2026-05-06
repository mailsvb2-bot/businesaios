from __future__ import annotations

from core.product.types import GuardVerdict, RoadmapCapacity


class CapacityDataGuard:
    def check(self, capacity: RoadmapCapacity) -> GuardVerdict:
        if capacity.max_now_items < 0:
            return GuardVerdict(False, "negative_now_capacity", "max_now_items must be >= 0")
        if capacity.max_next_items < 0:
            return GuardVerdict(False, "negative_next_capacity", "max_next_items must be >= 0")
        if capacity.max_later_items < 0:
            return GuardVerdict(False, "negative_later_capacity", "max_later_items must be >= 0")
        return GuardVerdict(True, "ok", "Roadmap capacity is structurally valid")
