from __future__ import annotations

from application.business_autonomy.business_connector_framework import ConnectorOnboardingService, StaticTrustOnboarding
from application.business_autonomy.distributed_capability_trust_registry import DistributedBusinessRegistry
from application.business_autonomy.provider_admin_contract import ProviderCredentialSubmission
from application.business_autonomy.provider_admin_service import ProviderAdminService
from runtime.business_autonomy.bootstrap import (
    StaticGovernanceEnablement,
    StaticPersistenceSurface,
    _build_typed_channel_registry,
)
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore, FileRegionRouteState
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.business_autonomy.provider_response_parsers import ProviderResponseParsers
from runtime.business_autonomy.provider_vendor_transports import build_provider_vendor_transports
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



def test_provider_response_parser_describes_known_fields(tmp_path):
    service = _service(tmp_path)
    parser = service.describe_provider_response_parser(provider_key='shopify')
    assert parser['supported'] is True
    assert 'orders' in parser['known_fields']



def test_provider_sync_history_is_persisted_and_listable(tmp_path):
    service = _service(tmp_path)
    service.activate_provider(ProviderCredentialSubmission(
        tenant_id='tenant-a',
        business_id='shop-a',
        provider_key='shopify',
        ownership_key='owner:shop-a',
        requested_by='owner-user',
        external_ref='shop://a',
        metadata={'probe_mode': 'dry_run'},
        secrets={'admin_access_token': 'token', 'webhook_secret': 'whsec'},
    ))
    result = service.trigger_provider_sync(
        tenant_id='tenant-a',
        business_id='shop-a',
        provider_key='shopify',
        operation='catalog_sync',
        mode='dry_run',
    )
    assert result['status'] == 'dry_run_ready'
    history = service.list_provider_sync_history(tenant_id='tenant-a', business_id='shop-a', provider_key='shopify')
    assert history
    assert history[0]['provider_key'] == 'shopify'
    assert history[0]['operation'] == 'catalog_sync'



def test_provider_response_parser_extracts_cursor_and_errors():
    parser = ProviderResponseParsers()
    provider = type('P', (), {'provider_key': 'hubspot'})()
    parsed = parser.parse(provider=provider, operation='contact_sync', response={'http_status': 200, 'response_body': '{"results": [{"id": "1"}], "paging": {"next": "cursor-2"}}'})
    assert parsed['resource_count'] == 1
    assert parsed['next_cursor'] == 'cursor-2'
