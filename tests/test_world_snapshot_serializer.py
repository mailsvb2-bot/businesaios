from __future__ import annotations

from core.world_model.serializers.world_snapshot_serializer import JsonReadyWorldSnapshotSerializer
from core.world_model.service import WorldModelService
from core.world_model.types import WorldModelBuildInput


def test_world_snapshot_serializer_is_deterministic() -> None:
    service = WorldModelService()
    serializer = JsonReadyWorldSnapshotSerializer()
    result = service.build_snapshot(build_input=WorldModelBuildInput(tenant_id="t1", business_id="b1", customer_id="c1", product_id="p1", channel="telegram", geo="NL", now_ms=1710000000000))
    assert result.snapshot is not None
    assert serializer.to_canonical_json(result.snapshot) == serializer.to_canonical_json(result.snapshot)
