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


def test_provider_admin_handlers_forward_customer_event_store_only_when_wired() -> None:
    service = _ProviderService()
    event_store = object()
    seen = []

    def factory(**kwargs):
        seen.append(kwargs)
        return service

    handlers = ProviderAdminRouteHandlers(service_factory=factory, customer_event_store=event_store)
    handlers.list_provider_runtime_incidents(tenant_id='tenant-a', business_id='business-a', provider_key='vk_messaging')
    assert seen == [{'business_id': 'business-a', 'customer_event_store': event_store}]


def test_provider_admin_customer_read_model_uses_canonical_registry_and_event_store() -> None:
    from crm import CustomerRegistry
    from reliability.idempotency_store import InMemoryIdempotencyStore
    from runtime.platform.event_store.memory_event_store import MemoryEventStore
    from security.secret_vault import InMemorySecretVault
    events = MemoryEventStore()
    registry = CustomerRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore(), pii_vault=InMemorySecretVault())
    record = registry.ensure_customer_identity(tenant_id='tenant-a', business_id='business-a', channel='vk', external_subject='42', display_name='Anna', occurred_at_ms=100)
    registry.record_contact(tenant_id='tenant-a', business_id='business-a', customer_id=record.customer.customer_id, channel='vk', external_subject='42', contact_id='msg-1', occurred_at_ms=110)
    service = _ProviderService()
    service.customer_registry = registry
    handlers = ProviderAdminRouteHandlers(service_factory=lambda **_: service, customer_event_store=events)
    detail = handlers.get_business_customers(tenant_id='tenant-a', business_id='business-a', customer_id=record.customer.customer_id)
    assert detail['count'] == 1 and detail['customers'][0]['identities'][0]['external_subject'] == '42'
    assert [row['kind'] for row in detail['timeline']['entries']] == ['customer.created', 'customer.identity.attached', 'customer.contact.observed']
