from __future__ import annotations

from core.world_model.enums import ReaderKind
from core.world_model.service import WorldModelService
from core.world_model.types import ReadResult, WorldModelBuildInput


class StaleCustomerReader:
    def read(self, *, build_input: WorldModelBuildInput) -> ReadResult[dict]:
        return ReadResult(reader=ReaderKind.CUSTOMER, payload={"customer_id": build_input.customer_id, "segment": "known", "stage": "known", "sessions_30d": 5, "purchases_30d": 1, "last_seen_at_ms": build_input.now_ms - 99999999, "traits": {}}, observed_at_ms=build_input.now_ms - 99999999, source="stale_customer_reader", metadata={})


def test_world_snapshot_rejects_stale_signal() -> None:
    service = WorldModelService(customer_reader=StaleCustomerReader())
    result = service.build_snapshot(build_input=WorldModelBuildInput(tenant_id="t1", business_id="b1", customer_id="c1", product_id="p1", channel="telegram", geo="NL", now_ms=1710000000000))
    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.reason == "stale_signal"
    assert result.rejection.details["event_type"] == "world_snapshot_rejected@v1"
