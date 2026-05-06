from entrypoints.api.admin_route_handlers import AdminRouteHandlers


def test_admin_route_handlers_expose_luxury_platform_admin_surfaces() -> None:
    handlers = AdminRouteHandlers()
    deps = handlers.get_platform_dependency_graph()
    remediation = handlers.get_platform_remediation_plan()
    diff = handlers.get_platform_risk_diff(tenant_id='tenant-demo')
    ownership = handlers.get_platform_ownership_graph()
    patches = handlers.get_platform_patch_suggestions()
    stops = handlers.get_platform_stop_conditions()
    workflow = handlers.get_platform_remediation_workflow(file_path='application/admin/platform_control_center_service.py', risk_type='large_module')
    assert 'dependency_rows' in deps
    assert 'remediation_rows' in remediation
    assert 'snapshot_available' in diff
    assert 'ownership_rows' in ownership
    assert 'patch_suggestions' in patches
    assert 'stop_conditions' in stops
    assert workflow['workflow_steps']


def test_admin_route_handlers_expose_ultra_platform_admin_surfaces() -> None:
    handlers = AdminRouteHandlers()
    snapshot = handlers.get_platform_snapshot_diff_view(tenant_id='tenant-demo')
    passport = handlers.get_platform_file_passport(file_path='application/admin/platform_control_center_service.py')
    drilldown = handlers.get_platform_ownership_drilldown(block='application')
    maturity = handlers.get_platform_maturity_trends(tenant_id='tenant-demo')
    run = handlers.run_platform_remediation(file_path='application/admin/platform_control_center_service.py', risk_type='large_module')
    widgets = handlers.get_platform_live_widgets(tenant_id='tenant-demo', business_id='site-alpha')
    conflicts = handlers.get_platform_visual_conflicts()
    layout = handlers.save_platform_dashboard_layout(tenant_id='tenant-demo', layout={'widgets': [{'widget_key': 'fleet_summary_live'}]})
    assert 'code_diff_rows' in snapshot
    assert passport['file_path'] == 'application/admin/platform_control_center_service.py'
    assert drilldown['block'] == 'application'
    assert 'trend_rows' in maturity
    assert run['status'] == 'prepared'
    assert widgets['polling']['enabled'] is True
    assert 'visual_conflict_map' in conflicts
    assert layout['layout']['mode'] == 'drag_drop_dashboard'
