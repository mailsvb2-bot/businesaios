from __future__ import annotations

from app.web.pages.platform_control_center import PlatformControlCenterPage


def test_platform_control_center_page_exposes_widget_runtime_hooks():
    page = PlatformControlCenterPage().build({'tenant_id': 'tenant-a', 'business_id': 'biz-1', 'provider_rows': (), 'summary_cards': ()})
    payload = page['payload']
    assert payload['actions']['widget_runtime_endpoint'] == '/control-plane/admin/platform-widget-runtime'
    assert payload['ui_schema']['asset_bundle']['runtime_hook_js'] == '/web/static/platform_admin_runtime_hooks.js'
    assert 'live_renderers' in payload
