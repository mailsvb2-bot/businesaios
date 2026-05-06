from __future__ import annotations

from core.world_model.enums import ReaderKind
from core.world_model.types import ReadResult, WorldModelBuildInput


class DefaultProductReader:
    def read(self, *, build_input: WorldModelBuildInput) -> ReadResult[dict]:
        return ReadResult(
            reader=ReaderKind.PRODUCT,
            payload={"product_id": build_input.product_id, "title": build_input.product_id, "price": None, "margin": None, "inventory_status": "unknown", "attributes": {}},
            observed_at_ms=build_input.now_ms,
            source="default_product_reader",
            metadata={"mode": "default"},
        )
