from __future__ import annotations

from interfaces.api.business_autonomy_route_handlers import build_business_autonomy_route_handlers


def test_demand_gravity_admin_surface_is_visible_without_execution_power() -> None:
    handlers = build_business_autonomy_route_handlers(stack={})
    surface = handlers.get_demand_gravity_surface(tenant_id="tenant-a")

    assert surface["surface"] == "demand_gravity"
    assert surface["decision_owner"] == "DecisionCore"
    assert surface["execution_owner"] == "canonical_execution_pipeline"
    assert surface["hard_guards"]["can_decide"] is False
    assert surface["hard_guards"]["can_execute"] is False
    assert surface["hard_guards"]["can_rank_channels"] is False
    assert surface["hard_guards"]["can_allocate_budget"] is False
    assert surface["hard_guards"]["requires_admin_visibility"] is True
