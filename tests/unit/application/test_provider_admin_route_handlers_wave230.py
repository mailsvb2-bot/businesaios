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


def test_provider_admin_route_handlers_expose_rotate_and_sync(tmp_path):
    handlers = _Handlers(_service(tmp_path))
    activated = handlers.activate_provider(payload={
        'tenant_id': 'tenant-a',
        'business_id': 'shop-a',
        'provider_key': 'shopify',
        'ownership_key': 'owner:shop-a',
        'requested_by': 'owner-user',
        'external_ref': 'shop://a',
        'secrets': {'admin_access_token': 'old-token', 'webhook_secret': 'whsec'},
        'metadata': {'probe_mode': 'dry_run'},
    })
    assert activated['connected'] is True
    rotated = handlers.rotate_provider(payload={
        'tenant_id': 'tenant-a',
        'business_id': 'shop-a',
        'provider_key': 'shopify',
        'requested_by': 'owner-user',
        'secrets': {'admin_access_token': 'new-token'},
    })
    assert rotated['metadata']['secret_lifecycle']['last_action'] == 'rotated'
    sync_result = handlers.trigger_provider_sync(payload={
        'tenant_id': 'tenant-a',
        'business_id': 'shop-a',
        'provider_key': 'shopify',
        'operation': 'catalog_sync',
        'mode': 'dry_run',
    })
    assert sync_result['status'] == 'dry_run_ready'



def test_provider_admin_route_handlers_expose_secret_history_and_runtime_routes(tmp_path):
    handlers = _Handlers(_service(tmp_path))
    handlers.activate_provider(payload={
        'tenant_id': 'tenant-a',
        'business_id': 'shop-a',
        'provider_key': 'shopify',
        'ownership_key': 'owner:shop-a',
        'requested_by': 'owner-user',
        'external_ref': 'shop://a',
        'secrets': {'admin_access_token': 'old-token', 'webhook_secret': 'whsec'},
        'metadata': {'probe_mode': 'dry_run'},
    })
    handlers.rotate_provider(payload={
        'tenant_id': 'tenant-a',
        'business_id': 'shop-a',
        'provider_key': 'shopify',
        'requested_by': 'owner-user',
        'secrets': {'admin_access_token': 'new-token'},
    })
    history = handlers.list_provider_secret_history(tenant_id='tenant-a', business_id='shop-a', provider_key='shopify')
    assert history['versions']
    version = next(item['version'] for item in history['versions'] if item['secret_name'] == 'admin_access_token' and item['version'] != 'current')
    rolled = handlers.rollback_provider_secret(payload={'tenant_id': 'tenant-a', 'business_id': 'shop-a', 'provider_key': 'shopify', 'secret_name': 'admin_access_token', 'version': version})
    assert rolled['status']['connected'] is True
    routes = handlers.get_provider_runtime_routes(provider_key='shopify')
    assert routes['transport_binding']['provider_key'] == 'shopify'
    assert 'path_template' in routes['webhook_route']
