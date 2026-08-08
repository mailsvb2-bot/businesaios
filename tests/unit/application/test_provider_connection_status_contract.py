from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter

from adapters.api.fastapi.business_workspace_provider_routes import register_business_workspace_provider_routes
from entrypoints.api.provider_admin_route_handlers import ProviderAdminRouteHandlers


class _Service:
    def list_provider_definitions(self):
        return (SimpleNamespace(provider_key='shopify', title='Shopify', connector_id='shopify.store', channel_kind=SimpleNamespace(value='commerce'), domain='commerce', description='Store', secret_fields=()),)

    def list_activation_statuses(self, *, tenant_id: str, business_id: str):
        return (SimpleNamespace(provider_key='shopify', connected=True, onboarding_ready=True, secret_fields_bound=('shopify.store.admin_access_token',), last_updated_utc='2026-08-07T00:00:00+00:00', metadata={'health_probe': {'status': 'ready_for_credentials', 'probe_mode': 'dry_run'}, 'runtime_plan': {'read_operations': ['catalog_sync'], 'write_operations': ['order_update']}}),)


def test_provider_catalog_exposes_truthful_connection_status_and_safe_actions(monkeypatch) -> None:
    monkeypatch.setattr(ProviderAdminRouteHandlers, '_service', lambda self, business_id: _Service())
    row = ProviderAdminRouteHandlers().list_provider_catalog(tenant_id='tenant-a', business_id='shop-a')['providers'][0]
    assert row['connected'] is True
    assert row['onboarding_ready'] is True
    assert row['credential_state'] == 'bound'
    assert row['health_probe']['status'] == 'ready_for_credentials'
    assert row['runtime_plan']['read_operations'] == ['catalog_sync']
    assert row['write_actions_enabled'] is False
    assert row['actions'] == {'activate': '/control-plane/provider-admin/activate', 'probe': '/control-plane/provider-runtime/live-probe', 'read_sync': '/control-plane/provider-runtime/sync', 'sync_history': '/control-plane/provider-runtime/sync-history'}


def test_owner_workspace_replaces_dead_provider_token_handoff() -> None:
    router = APIRouter()
    register_business_workspace_provider_routes(router=router, auth_bundle=object(), provider_admin_handlers=ProviderAdminRouteHandlers())
    routes = {(route.path, tuple(sorted(route.methods))) for route in router.routes}
    assert ('/business-workspace/providers', ('GET',)) in routes
    assert ('/business-workspace/providers', ('POST',)) in routes
    assert all(path != '/web/provider-tokens' for path, _ in routes)
