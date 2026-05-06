from __future__ import annotations

import pytest

from core.world_model.service import WorldModelService
from core.world_model.types import WorldModelBuildInput


def test_world_snapshot_rejects_decision_like_context_keys() -> None:
    service = WorldModelService()
    with pytest.raises(Exception) as exc:
        service.build_snapshot(build_input=WorldModelBuildInput(tenant_id="t1", business_id="b1", customer_id="c1", product_id="p1", channel="telegram", geo="NL", now_ms=1710000000000, context={"action": "launch_campaign"}))
    assert "forbidden decision-like context key" in str(exc.value)
