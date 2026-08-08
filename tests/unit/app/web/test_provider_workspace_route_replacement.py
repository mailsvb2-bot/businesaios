from __future__ import annotations

from app.web.pages.provider_tokens_admin import ProviderTokensAdminPage
from app.web.routes import Routes


def test_dead_provider_tokens_route_is_replaced_by_real_business_workspace() -> None:
    routes = Routes().build_default(tenant_id='tenant-a')['payload']['routes']
    assert '/web/provider-tokens' not in {row['path'] for row in routes}
    legacy = ProviderTokensAdminPage().build({'tenant_id': 'tenant-a'})['payload']
    assert legacy['deprecated'] is True
    assert legacy['replacement_path'] == '/business-workspace/providers'
    assert legacy['write_actions_enabled'] is False
