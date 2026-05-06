from __future__ import annotations

from core.world_model.enums import ReaderKind
from core.world_model.types import ReadResult, WorldModelBuildInput


class DefaultCustomerReader:
    def read(self, *, build_input: WorldModelBuildInput) -> ReadResult[dict]:
        return ReadResult(
            reader=ReaderKind.CUSTOMER,
            payload={"customer_id": build_input.customer_id, "stage": "unknown", "segment": "unknown", "sessions_30d": 0, "purchases_30d": 0, "last_seen_at_ms": None, "traits": {}},
            observed_at_ms=build_input.now_ms,
            source="default_customer_reader",
            metadata={"mode": "default"},
        )
