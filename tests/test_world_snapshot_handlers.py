from __future__ import annotations

from core.world_model.service import WorldModelService
from core.world_model.types import WorldModelBuildInput
from runtime.handlers.world_snapshot_build import handle_world_snapshot_build
from runtime.handlers.world_snapshot_explain import handle_world_snapshot_explain


def test_world_snapshot_handlers_are_thin_and_work() -> None:
    service = WorldModelService()
    result = handle_world_snapshot_build(
        service,
        WorldModelBuildInput(
            tenant_id="t1",
            business_id="b1",
            customer_id="c1",
            product_id="p1",
            channel="telegram",
            geo="NL",
            now_ms=1710000000000,
        ),
    )
    assert result.accepted is True
    assert result.snapshot is not None
    explanation = handle_world_snapshot_explain(result.snapshot)
    assert "summary" in explanation


from core.world_model.builders.world_snapshot_builder import build_empty_world_snapshot
from core.world_model.explainers.world_snapshot_explainer import explain_world_snapshot
from core.world_model.types import WorldSnapshotRequest
from runtime.handlers.world_model_build import handle_world_model_build


class _DummyBuilder:
    def build(self, request: WorldSnapshotRequest):
        return build_empty_world_snapshot(request)


def test_world_snapshot_handler_contract_preserves_empty_snapshot_shape() -> None:
    snapshot = handle_world_model_build(_DummyBuilder(), "t1", "corr1")
    text = explain_world_snapshot(snapshot)
    assert snapshot.tenant_id == "t1"
    assert snapshot.correlation_id == "corr1"
    assert "confidence=0.0" in text
