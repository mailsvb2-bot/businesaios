from app.web.pages.platform_control_center import PlatformControlCenterPage


def test_platform_control_center_page_builds_expected_actions() -> None:
    page = PlatformControlCenterPage()
    payload = page.build({'tenant_id': 'tenant-demo', 'business_id': 'biz-1', 'summary_cards': [{'title': 'x', 'value': 1}]})
    body = payload['payload']
    assert body['tenant_id'] == 'tenant-demo'
    assert body['actions']['overview_endpoint'] == '/control-plane/admin/platform-overview'
    assert body['ui_schema']['primary_buttons']
