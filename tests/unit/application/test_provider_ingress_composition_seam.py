from __future__ import annotations

from fastapi import APIRouter

from adapters.api.fastapi.provider_webhook_routes import register_provider_webhook_routes
from entrypoints.api.provider_admin_route_handlers import ProviderAdminRouteHandlers


class _ProviderService:
    def __init__(self) -> None:
        self.calls = []

    def list_provider_runtime_incidents(self, **kwargs):
        self.calls.append(kwargs)
        return ({'status': 'ok'},)


def test_provider_admin_handlers_accept_injected_service_factory() -> None:
    service = _ProviderService()
    seen = []

    def factory(*, business_id: str):
        seen.append(business_id)
        return service

    rows = ProviderAdminRouteHandlers(service_factory=factory).list_provider_runtime_incidents(
        tenant_id='tenant-a', business_id='business-a', provider_key='vk_messaging'
    )
    assert seen == ['business-a']
    assert rows['incidents'] == [{'status': 'ok'}]
    assert service.calls[0]['tenant_id'] == 'tenant-a'


def test_provider_webhook_registrar_owns_only_canonical_public_post_route() -> None:
    router = APIRouter()
    register_provider_webhook_routes(router=router, provider_admin_handlers=object())
    routes = [(route.path, tuple(sorted(route.methods))) for route in router.routes]
    assert routes == [('/providers/webhook/{tenant_id}/{business_id}/{provider_key}', ('POST',))]
