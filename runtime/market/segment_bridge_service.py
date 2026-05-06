from __future__ import annotations

from dataclasses import dataclass

from runtime.behavior import CohortAggregate, segment_direction_score
from runtime.runtime_observability import RuntimeObservability


@dataclass
class SegmentBridgeService:
    observability: RuntimeObservability

    def inspect(self, aggregates: tuple[CohortAggregate, ...]) -> dict[str, float]:
        if not aggregates:
            return {"segment_count": 0.0, "mean_segment_direction": 0.0}
        direction_scores = [segment_direction_score(item) for item in aggregates]
        mean_direction = sum(direction_scores) / len(direction_scores)
        self.observability.record_model_snapshot(
            model_name="segment_bridge",
            metric_name="mean_segment_direction",
            metric_value=mean_direction,
        )
        return {
            "segment_count": float(len(aggregates)),
            "mean_segment_direction": float(mean_direction),
        }
