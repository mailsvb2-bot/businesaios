from __future__ import annotations

from core.world_model.enums import ReaderKind
from core.world_model.types import ReadResult, WorldModelBuildInput


class DefaultRevenueReader:
    def read(self, *, build_input: WorldModelBuildInput) -> ReadResult[dict]:
        return ReadResult(
            reader=ReaderKind.REVENUE,
            payload={"revenue_7d": 0.0, "orders_7d": 0, "conversion_rate": None},
            observed_at_ms=build_input.now_ms,
            source="default_revenue_reader",
            metadata={"mode": "default"},
        )
