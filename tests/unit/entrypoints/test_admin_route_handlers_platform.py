from entrypoints.api.admin_route_handlers import AdminRouteHandlers


def test_admin_route_handlers_platform_surfaces() -> None:
    handlers = AdminRouteHandlers()
    overview = handlers.get_platform_overview(tenant_id='tenant-demo', business_id='site-alpha')
    risks = handlers.get_platform_risk_registry()
    assert overview['tenant_id'] == 'tenant-demo'
    assert 'summary_cards' in overview
    assert 'risk_rows' in overview
    assert 'severity_counts' in risks
