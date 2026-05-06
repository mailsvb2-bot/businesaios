from application.admin.platform_control_center_service import PlatformControlCenterService


def test_platform_control_center_overview_exposes_risks_and_blocks() -> None:
    service = PlatformControlCenterService.for_repo()
    payload = service.build_overview(tenant_id='tenant-demo', business_id='site-alpha')
    assert payload['tenant_id'] == 'tenant-demo'
    assert payload['business_id'] == 'site-alpha'
    assert payload['summary_cards']
    assert payload['block_rows']
    assert 'graphs' in payload
    assert 'risk_rows' in payload
    assert payload['canon_status']['admin_surface_required_for_new_features'] is True


def test_platform_risk_registry_has_counts() -> None:
    service = PlatformControlCenterService.for_repo()
    payload = service.build_risk_registry()
    assert payload['count'] >= 0
    assert set(payload['severity_counts']) == {'critical', 'major', 'minor'}
