from __future__ import annotations

from core.world_model.enums import ReaderKind
from core.world_model.types import ReadResult, WorldModelBuildInput


class DefaultMarketReader:
    def read(self, *, build_input: WorldModelBuildInput) -> ReadResult[dict]:
        return ReadResult(
            reader=ReaderKind.MARKET,
            payload={"channel": build_input.channel, "geo": build_input.geo, "competition_index": None, "cpm": None, "seasonality": "unknown"},
            observed_at_ms=build_input.now_ms,
            source="default_market_reader",
            metadata={"mode": "default"},
        )
