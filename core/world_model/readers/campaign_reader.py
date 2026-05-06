from __future__ import annotations

from core.world_model.enums import ReaderKind
from core.world_model.types import ReadResult, WorldModelBuildInput


class DefaultCampaignReader:
    def read(self, *, build_input: WorldModelBuildInput) -> ReadResult[dict]:
        return ReadResult(
            reader=ReaderKind.CAMPAIGN,
            payload={"campaign_pressure": None, "active_campaigns": 0, "spend_24h": 0.0},
            observed_at_ms=build_input.now_ms,
            source="default_campaign_reader",
            metadata={"mode": "default"},
        )
