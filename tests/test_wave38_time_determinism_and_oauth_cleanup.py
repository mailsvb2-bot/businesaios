from core.economics.ltv_world_model import LTVModel, UserState, WorldModel
from core.world_model.service import WorldModelService
from core.world_model.types import WorldModelBuildInput


def test_ltv_world_model_build_is_deterministic_without_wall_clock() -> None:
    user = UserState(user_id="u1", sessions=4, payments=10.0, last_seen=123.0)
    model = WorldModel(LTVModel())
    first = model.build(user)
    second = model.build(user)
    assert first.predicted_ltv == second.predicted_ltv


def test_world_model_service_uses_build_input_now_ms_as_built_at() -> None:
    service = WorldModelService()
    result = service.build_snapshot(
        build_input=WorldModelBuildInput(
            tenant_id="t1",
            business_id="b1",
            customer_id="c1",
            product_id="p1",
            channel="telegram",
            geo="NL",
            now_ms=1710000000123,
        )
    )
    assert result.accepted is True
    assert result.snapshot is not None
    assert result.snapshot.built_at_ms == 1710000000123
