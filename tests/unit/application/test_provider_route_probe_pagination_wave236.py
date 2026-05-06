from __future__ import annotations

from entrypoints.api.provider_admin_route_handlers import ProviderAdminRouteHandlers


class _Svc:
    def describe_provider_runtime_routes(self, *, provider_key: str):
        return {
            'provider_key': provider_key,
            'live_probe_endpoint': '/control-plane/provider-runtime/live-probe',
            'pagination_endpoint': '/control-plane/provider-runtime/paginate',
        }


def test_provider_route_runtime_routes_include_probe_and_pagination(monkeypatch):
    monkeypatch.setattr(ProviderAdminRouteHandlers, '_service', lambda self, business_id: _Svc())
    handlers = ProviderAdminRouteHandlers()
    routes = handlers.get_provider_runtime_routes(provider_key='shopify')
    assert 'live_probe_endpoint' in routes
    assert 'pagination_endpoint' in routes
