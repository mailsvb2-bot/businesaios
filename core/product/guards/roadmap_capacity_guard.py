from __future__ import annotations

from core.product.enums import RoadmapBucket
from core.product.types import GuardVerdict, RoadmapCapacity, RoadmapProposal


class RoadmapCapacityGuard:
    def check(self, proposal: RoadmapProposal, capacity: RoadmapCapacity) -> GuardVerdict:
        now_count = next_count = later_count = 0
        for item in proposal.items:
            if item.bucket == RoadmapBucket.NOW:
                now_count += 1
            elif item.bucket == RoadmapBucket.NEXT:
                next_count += 1
            elif item.bucket == RoadmapBucket.LATER:
                later_count += 1
        if now_count > capacity.max_now_items:
            return GuardVerdict(False, "roadmap_now_capacity_exceeded", "NOW bucket exceeds allowed capacity")
        if next_count > capacity.max_next_items:
            return GuardVerdict(False, "roadmap_next_capacity_exceeded", "NEXT bucket exceeds allowed capacity")
        if later_count > capacity.max_later_items:
            return GuardVerdict(False, "roadmap_later_capacity_exceeded", "LATER bucket exceeds allowed capacity")
        return GuardVerdict(True, "ok", "Roadmap capacity is within limits")
