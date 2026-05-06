from __future__ import annotations

from core.product.enums import RoadmapBucket
from core.product.types import RoadmapProposal


class RoadmapProjection:
    def project(self, proposal: RoadmapProposal) -> dict[str, list[str]]:
        result = {RoadmapBucket.NOW.value: [], RoadmapBucket.NEXT.value: [], RoadmapBucket.LATER.value: [], RoadmapBucket.HOLD.value: []}
        for item in proposal.items:
            result[item.bucket.value].append(item.feature_id)
        return result
