from __future__ import annotations

from core.product.enums import RoadmapBucket
from core.product.types import FeatureScore, RoadmapCapacity, RoadmapItem


class RoadmapPriorityPolicy:
    def assign(self, scores: list[FeatureScore], capacity: RoadmapCapacity) -> list[RoadmapItem]:
        ordered = sorted(scores, key=lambda item: (-item.total_score, item.feature_id))
        items: list[RoadmapItem] = []

        now_cutoff = capacity.max_now_items
        next_cutoff = now_cutoff + capacity.max_next_items
        later_cutoff = next_cutoff + capacity.max_later_items

        for index, score in enumerate(ordered):
            if index < now_cutoff:
                bucket = RoadmapBucket.NOW
            elif index < next_cutoff:
                bucket = RoadmapBucket.NEXT
            elif index < later_cutoff:
                bucket = RoadmapBucket.LATER
            else:
                bucket = RoadmapBucket.HOLD

            items.append(
                RoadmapItem(
                    feature_id=score.feature_id,
                    bucket=bucket,
                    priority_rank=index + 1,
                    rationale=f"score={score.total_score:.4f}",
                )
            )
        return items
