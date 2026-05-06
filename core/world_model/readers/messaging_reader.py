from __future__ import annotations

from core.world_model.enums import ReaderKind
from core.world_model.types import ReadResult, WorldModelBuildInput


class DefaultMessagingReader:
    def read(self, *, build_input: WorldModelBuildInput) -> ReadResult[dict]:
        return ReadResult(
            reader=ReaderKind.MESSAGING,
            payload={"last_channel": build_input.channel, "delivery_rate_7d": None, "reply_rate_7d": None},
            observed_at_ms=build_input.now_ms,
            source="default_messaging_reader",
            metadata={"mode": "default"},
        )
