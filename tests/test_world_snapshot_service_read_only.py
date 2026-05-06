from __future__ import annotations

from core.world_model.service import WorldModelService
from core.world_model.types import WorldModelBuildInput


def test_world_snapshot_service_builds_read_only_snapshot() -> None:
    service = WorldModelService()
    result = service.build_snapshot(build_input=WorldModelBuildInput(tenant_id="t1", business_id="b1", customer_id="c1", product_id="p1", channel="telegram", geo="NL", now_ms=1710000000000))
    assert result.accepted is True
    assert result.snapshot is not None
    assert result.snapshot.explain["contract"]["read_only"] is True
    assert result.snapshot.explain["contract"]["decision_issuer"] == "none"
    assert result.snapshot.explain["contract"]["role"] == "state_snapshot_only"
