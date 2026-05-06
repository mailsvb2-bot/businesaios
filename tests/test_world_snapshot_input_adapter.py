from __future__ import annotations

from bootstrap.world_snapshot_input_adapter import build_world_snapshot_input


def test_world_snapshot_input_adapter_maps_payload() -> None:
    build_input = build_world_snapshot_input(payload={"world_state": {"tenant_id": "t1", "business_id": "b1", "customer_id": "c1", "product_id": "p1", "channel": "telegram", "geo": "NL"}, "context": {"correlation_id": "x"}}, now_ms=1710000000000)
    assert build_input.tenant_id == "t1"
    assert build_input.business_id == "b1"
    assert build_input.context["correlation_id"] == "x"
