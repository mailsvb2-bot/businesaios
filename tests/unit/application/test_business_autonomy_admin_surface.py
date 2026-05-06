from entrypoints.api.admin_route_handlers import AdminRouteHandlers


def test_admin_route_handlers_expose_business_autonomy_overview() -> None:
    handlers = AdminRouteHandlers()
    overview = handlers.get_business_autonomy_overview(business_id="metrotherapy")
    assert overview["business_id"] == "metrotherapy"
    assert "readiness" in overview
    assert "observability" in overview
    assert "capabilities" in overview
    assert "trust" in overview


def test_admin_route_handlers_export_business_autonomy_bundle() -> None:
    handlers = AdminRouteHandlers()
    exported = handlers.export_business_autonomy_bundle(business_id="metrotherapy")
    assert exported["business_id"] == "metrotherapy"
    assert exported["observability_bundle"]["path"].endswith('.json')
    assert exported["audit_bundle"]["path"].endswith('.json')
