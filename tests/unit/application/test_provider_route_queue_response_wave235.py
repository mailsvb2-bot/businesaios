from __future__ import annotations

from application.business_autonomy.provider_admin_service import ProviderAdminService
from application.business_autonomy.business_connector_framework import ConnectorOnboardingService, StaticTrustOnboarding
from application.business_autonomy.distributed_capability_trust_registry import DistributedBusinessRegistry
from entrypoints.api.provider_admin_route_handlers import ProviderAdminRouteHandlers
from runtime.business_autonomy.bootstrap import StaticGovernanceEnablement, StaticPersistenceSurface, _build_typed_channel_registry
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore, FileRegionRouteState
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
from security.connector_secret_scope import ConnectorSecretScope
from security.secret_vault import InMemorySecretVault


class _Handlers(ProviderAdminRouteHandlers):
    def __init__(self, service: ProviderAdminService) -> None:
        object.__setattr__(self, '_svc', service)

    def _service(self, business_id: str):
        return self._svc



def _service(tmp_path):
    documents = FileDistributedDocumentStore(tmp_path / 'docs')
    registry = DistributedBusinessRegistry(documents=documents)
    onboarding = ConnectorOnboardingService(
        adapter_registry=_build_typed_channel_registry(),
        business_registry=registry,
        trust_onboarding=StaticTrustOnboarding(),
        governance_enablement=StaticGovernanceEnablement(),
        persistence_surface=StaticPersistenceSurface(),
    )
    return ProviderAdminService(
        onboarding_service=onboarding,
        secret_vault=InMemorySecretVault(),
        connector_secret_scope=ConnectorSecretScope(),
        activation_store=FileProviderActivationStore(documents),
        route_state=FileRegionRouteState(documents),
    )



def test_route_handlers_expose_sync_history_and_response_parser(tmp_path):
    handlers = _Handlers(_service(tmp_path))
    handlers.activate_provider(payload={
        'tenant_id': 'tenant-a',
        'business_id': 'shop-a',
        'provider_key': 'shopify',
        'ownership_key': 'owner:shop-a',
        'requested_by': 'owner-user',
        'external_ref': 'shop://a',
        'secrets': {'admin_access_token': 'token', 'webhook_secret': 'whsec'},
        'metadata': {'probe_mode': 'dry_run'},
    })
    handlers.trigger_provider_sync(payload={
        'tenant_id': 'tenant-a',
        'business_id': 'shop-a',
        'provider_key': 'shopify',
        'operation': 'catalog_sync',
        'mode': 'dry_run',
    })
    history = handlers.list_provider_sync_history(tenant_id='tenant-a', business_id='shop-a', provider_key='shopify')
    parser = handlers.describe_provider_response_parser(provider_key='shopify')
    assert history['history']
    assert parser['supported'] is True
