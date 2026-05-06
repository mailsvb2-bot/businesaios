from app.web.pages.platform_control_center import PlatformControlCenterPage


def test_platform_page_exposes_luxury_admin_endpoints_and_sections() -> None:
    page = PlatformControlCenterPage()
    payload = page.build({'tenant_id': 'tenant-demo', 'business_id': 'site-alpha'})['payload']
    assert payload['actions']['dependency_graph_endpoint'] == '/control-plane/admin/platform-dependencies'
    assert payload['actions']['remediation_endpoint'] == '/control-plane/admin/platform-remediation'
    assert payload['actions']['ownership_endpoint'] == '/control-plane/admin/platform-ownership'
    assert payload['actions']['patch_suggestions_endpoint'] == '/control-plane/admin/platform-patch-suggestions'
    assert 'ownership_rows' in payload['ui_schema']['sections']
    assert 'patch_suggestions' in payload['ui_schema']['sections']
    assert 'stop_conditions' in payload['ui_schema']['sections']
    assert 'patch_suggestion_columns' in payload['ui_schema']


def test_platform_page_exposes_ultra_admin_actions() -> None:
    page = PlatformControlCenterPage()
    payload = page.build({'tenant_id': 'tenant-demo', 'business_id': 'site-alpha'})['payload']
    assert payload['actions']['snapshot_diff_view_endpoint'] == '/control-plane/admin/platform-snapshot-diff-view'
    assert payload['actions']['file_passport_endpoint'] == '/control-plane/admin/platform-file-passport'
    assert payload['actions']['ownership_drilldown_endpoint'] == '/control-plane/admin/platform-ownership-drilldown'
    assert payload['actions']['maturity_trends_endpoint'] == '/control-plane/admin/platform-maturity-trends'
    assert payload['actions']['remediation_run_endpoint'] == '/control-plane/admin/platform-remediation-run'
    assert payload['actions']['live_widgets_endpoint'] == '/control-plane/admin/platform-live-widgets'
    assert payload['actions']['visual_conflict_map_endpoint'] == '/control-plane/admin/platform-visual-conflicts'
    assert payload['actions']['dashboard_layout_endpoint'] == '/control-plane/admin/platform-dashboard-layout'
    assert 'snapshot_diff_view' in payload['ui_schema']['sections']
    assert 'block_maturity_trends' in payload['ui_schema']['sections']
    assert 'live_widget_bundle' in payload['ui_schema']['sections']
    assert 'visual_conflict_map' in payload['ui_schema']['sections']
    assert payload['ui_schema']['supports_drag_drop_layout'] is True
    assert payload['ui_schema']['supports_live_polling'] is True
