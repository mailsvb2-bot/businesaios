from __future__ import annotations

from application.business_autonomy.operator_admin_plane import FleetCard, FleetView
from interfaces.api.business_autonomy_route_handlers import BusinessAutonomyRouteHandlers


class _Plane:
    def get_fleet_view(self, limit: int = 100):
        return FleetView(
            fleet_cards=(FleetCard(title="Delayed Outcomes", value="1", status="degraded", detail="quarantined=1"),),
            delayed_outcome_quarantine_rows=({"business_id": "biz-a", "reason": "delayed_outcome_stale"},),
            export_surface={},
        )


def test_route_handlers_include_delayed_outcome_quarantine_rows() -> None:
    handlers = BusinessAutonomyRouteHandlers(stack={"operator_admin_plane": _Plane()})
    payload = handlers.get_fleet_view(limit=10)
    assert payload["delayed_outcome_quarantine_rows"][0]["business_id"] == "biz-a"
