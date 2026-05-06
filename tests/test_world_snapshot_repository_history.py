from __future__ import annotations

from core.world_model.service import WorldModelService
from core.world_model.types import WorldModelBuildInput


def test_world_snapshot_repository_keeps_history() -> None:
    service = WorldModelService()
    service.build_snapshot(build_input=WorldModelBuildInput(tenant_id="t1", business_id="b1", customer_id="c1", product_id="p1", channel="telegram", geo="NL", now_ms=1710000000000))
    service.build_snapshot(build_input=WorldModelBuildInput(tenant_id="t1", business_id="b1", customer_id="c1", product_id="p1", channel="telegram", geo="NL", now_ms=1710000000001))
    history = service.get_snapshot_history(tenant_id="t1", business_id="b1")
    assert len(history) == 2
