
from __future__ import annotations

from entrypoints.api.provider_admin_route_handlers import ProviderAdminRouteHandlers


def test_route_handler_exposes_incidents_and_queue_metrics(monkeypatch):
    class _Svc:
        def list_provider_runtime_incidents(self, **kwargs):
            return ({'status': 'live_execution_failed'},)
        def get_provider_queue_metrics(self, **kwargs):
            return {'pending': 1, 'claimed': 0, 'completed': 0, 'failed': 0}
    handlers = ProviderAdminRouteHandlers()
    monkeypatch.setattr(ProviderAdminRouteHandlers, '_service', lambda self, business_id: _Svc())
    incidents = handlers.list_provider_runtime_incidents(tenant_id='t', business_id='b', provider_key='p')
    assert incidents['incidents'][0]['status'] == 'live_execution_failed'
    metrics = handlers.get_provider_queue_metrics(tenant_id='t')
    assert metrics['pending'] == 1
