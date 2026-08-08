from __future__ import annotations

from app.web.pages import ADMIN_PAGES
from app.web.routes import Routes


def test_dead_provider_tokens_page_and_route_are_retired() -> None:
    routes = Routes().build_default(tenant_id='tenant-a')['payload']['routes']
    assert '/web/provider-tokens' not in {row['path'] for row in routes}
    assert 'ProviderTokensAdminPage' not in ADMIN_PAGES
