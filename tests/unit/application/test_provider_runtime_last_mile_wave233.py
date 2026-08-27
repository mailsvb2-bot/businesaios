from __future__ import annotations

from application.business_autonomy.business_connector_framework import ConnectorOnboardingService, StaticTrustOnboarding
from application.business_autonomy.distributed_capability_trust_registry import DistributedBusinessRegistry
from application.business_autonomy.provider_admin_contract import ProviderCredentialSubmission
from application.business_autonomy.provider_admin_service import ProviderAdminService
from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.bootstrap import (
    StaticGovernanceEnablement,
    StaticPersistenceSurface,
    _build_typed_channel_registry,
)
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore, FileRegionRouteState
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.business_autonomy.provider_vendor_transports import build_provider_vendor_transports
from runtime.business_autonomy.provider_webhook_route_registry import ProviderWebhookRouteRegistry
from security.connector_secret_scope import ConnectorSecretScope
from security.secret_vault import InMemorySecretVault


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


def test_shopify_vendor_transport_normalizes_catalog_payload(tmp_path):
    service = _service(tmp_path)
    service.activate_provider(ProviderCredentialSubmission(tenant_id='tenant-a', business_id='shop-a', provider_key='shopify', ownership_key='owner:shop-a', requested_by='owner-user', external_ref='shop://a', secrets={'admin_access_token': 'token', 'webhook_secret': 'whsec'}, metadata={'probe_mode': 'dry_run'}))
    provider = provider_map()['shopify']
    result = ProviderLiveSyncRuntime(service.secret_vault, transports=build_provider_vendor_transports()).run(provider=provider, tenant_id='tenant-a', business_id='shop-a', operation='catalog_sync', mode='live', payload={'shop': 'demo-shop', 'limit': '25'})
    response = dict(result.metadata).get('transport_response', {})
    assert response.get('normalized_payload', {}).get('limit') == 25


def test_webhook_registry_extracts_resource_id_from_shopify_body():
    provider = provider_map()['shopify']
    extracted = ProviderWebhookRouteRegistry().extract(provider, {'X-Shopify-Topic': 'orders/create'}, b'{"id": 123, "admin_graphql_api_id": "gid://shopify/Order/123"}')
    assert extracted['resource_id'] == '123'
    assert extracted['topic'] == 'orders/create'


def test_provider_retry_jobs_and_export_history_are_listable(tmp_path):
    service = _service(tmp_path)
    service.activate_provider(ProviderCredentialSubmission(tenant_id='tenant-a', business_id='shop-a', provider_key='shopify', ownership_key='owner:shop-a', requested_by='owner-user', external_ref='shop://a', secrets={'admin_access_token': 'token', 'webhook_secret': 'whsec'}, metadata={'probe_mode': 'dry_run'}))
    service.schedule_provider_retry(tenant_id='tenant-a', business_id='shop-a', provider_key='shopify', operation='catalog_sync', category='transport_timeout', retryable=True)
    provider = provider_map()['shopify']
    ProviderLiveSyncRuntime(service.secret_vault, transports=build_provider_vendor_transports()).run(provider=provider, tenant_id='tenant-a', business_id='shop-a', operation='catalog_sync', mode='dry_run')
    jobs = service.list_provider_retry_jobs(tenant_id='tenant-a', business_id='shop-a', provider_key='shopify')
    exports = service.list_provider_export_history(tenant_id='tenant-a', business_id='shop-a', provider_key='shopify')
    assert jobs and jobs[0]['provider_key'] == 'shopify'
    assert exports and exports[0]['provider_key'] == 'shopify'
