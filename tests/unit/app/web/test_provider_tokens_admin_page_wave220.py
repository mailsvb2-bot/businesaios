from __future__ import annotations

from app.web.pages.provider_tokens_admin import ProviderTokensAdminPage
from app.web.routes import Routes


def test_provider_tokens_page_contains_button_schema():
    payload = ProviderTokensAdminPage().build({'tenant_id': 'tenant-a', 'business_id': 'site-a', 'rows': ()})
    ui_schema = payload['payload']['ui_schema']
    labels = [item['label'] for item in ui_schema['primary_buttons']]
    assert 'Ввести токен для сайта' in labels
    assert payload['payload']['actions']['activate_endpoint'] == '/control-plane/provider-admin/activate'


def test_routes_include_provider_tokens_page():
    payload = Routes().build_default(tenant_id='tenant-a')
    paths = [row['path'] for row in payload['payload']['routes']]
    assert '/web/provider-tokens' in paths
