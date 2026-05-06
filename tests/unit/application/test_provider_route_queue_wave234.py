from __future__ import annotations

from entrypoints.api.provider_admin_route_handlers import ProviderAdminRouteHandlers


def test_provider_route_handlers_have_queue_methods():
    handlers = ProviderAdminRouteHandlers()
    assert callable(getattr(handlers, 'enqueue_provider_sync'))
    assert callable(getattr(handlers, 'tick_provider_sync_queue'))
    assert callable(getattr(handlers, 'describe_provider_live_client'))
