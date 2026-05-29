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


def test_vendor_transport_returns_prepared_live_request_for_shopify(tmp_path):
    service = _service(tmp_path)
    service.activate_provider(
        ProviderCredentialSubmission(tenant_id='tenant-a', business_id='shop-a', provider_key='shopify', ownership_key='owner:shop-a', requested_by='owner-user', external_ref='shop://a', secrets={'admin_access_token': 'shpat_test', 'webhook_secret': 'whsec'}, metadata={'probe_mode': 'dry_run'})
    )
    provider = provider_map()['shopify']
    result = ProviderLiveSyncRuntime(service.secret_vault, transports=build_provider_vendor_transports()).run(provider=provider, tenant_id='tenant-a', business_id='shop-a', operation='catalog_sync', mode='live', payload={'shop': 'demo-shop'})
    assert result.status == 'live_prepared_only'
    response = dict(result.metadata).get('transport_response', {})
    assert response.get('vendor_family') == 'shopify_admin_api'
    assert 'demo-shop' in response.get('request', {}).get('url_template', '')


def test_webhook_route_registry_extracts_shopify_headers():
    provider = provider_map()['shopify']
    registry = ProviderWebhookRouteRegistry()
    body = b'{}'
    extracted = registry.extract(provider, {'X-Shopify-Webhook-Id': 'evt-9', 'X-Shopify-Topic': 'orders/create', 'X-Shopify-Shop-Domain': 'demo.myshopify.com'}, body)
    assert extracted['event_key'] == 'evt-9'
    assert extracted['topic'] == 'orders/create'
    assert extracted['source_ref'] == 'demo.myshopify.com'


def test_mark_provider_secret_compromised_revokes_connector(tmp_path):
    service = _service(tmp_path)
    service.activate_provider(
        ProviderCredentialSubmission(tenant_id='tenant-a', business_id='shop-a', provider_key='shopify', ownership_key='owner:shop-a', requested_by='owner-user', external_ref='shop://a', secrets={'admin_access_token': 'token-old', 'webhook_secret': 'whsec'}, metadata={'probe_mode': 'dry_run'})
    )
    result = service.mark_provider_secret_compromised(tenant_id='tenant-a', business_id='shop-a', provider_key='shopify', secret_name='admin_access_token', reason='token_leaked')
    assert result['compromise']['status'] == 'marked_compromised'
    assert result['status'].connected is False
    assert dict(result['status'].metadata).get('secret_compromise', {}).get('reason') == 'token_leaked'


def test_schedule_provider_retry_returns_job(tmp_path):
    service = _service(tmp_path)
    result = service.schedule_provider_retry(tenant_id='tenant-a', business_id='shop-a', provider_key='shopify', operation='catalog_sync', category='transport_timeout', retryable=True)
    assert result['scheduled'] is True
    assert dict(result['metadata']).get('job', {}).get('provider_key') == 'shopify'
