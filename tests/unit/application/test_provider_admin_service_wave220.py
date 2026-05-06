from __future__ import annotations

from application.business_autonomy.business_connector_framework import ConnectorOnboardingService, StaticTrustOnboarding
from application.business_autonomy.provider_admin_service import ProviderAdminService
from application.business_autonomy.provider_admin_contract import ProviderCredentialSubmission
from runtime.business_autonomy.bootstrap import StaticGovernanceEnablement, StaticPersistenceSurface, _build_typed_channel_registry
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore, FileRegionRouteState
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
from application.business_autonomy.distributed_capability_trust_registry import DistributedBusinessRegistry
from security.connector_secret_scope import ConnectorSecretScope
from security.secret_vault import InMemorySecretVault


def test_provider_admin_service_stores_secrets_and_onboards_business(tmp_path):
    documents = FileDistributedDocumentStore(tmp_path / 'docs')
    registry = DistributedBusinessRegistry(documents=documents)
    onboarding = ConnectorOnboardingService(
        adapter_registry=_build_typed_channel_registry(),
        business_registry=registry,
        trust_onboarding=StaticTrustOnboarding(),
        governance_enablement=StaticGovernanceEnablement(),
        persistence_surface=StaticPersistenceSurface(),
    )
    service = ProviderAdminService(
        onboarding_service=onboarding,
        secret_vault=InMemorySecretVault(),
        connector_secret_scope=ConnectorSecretScope(),
        activation_store=FileProviderActivationStore(documents),
        route_state=FileRegionRouteState(documents),
    )
    status = service.activate_provider(
        ProviderCredentialSubmission(
            tenant_id='tenant-a',
            business_id='my-site',
            provider_key='generic_website',
            ownership_key='owner:my-site',
            requested_by='owner-user',
            external_ref='https://example.com',
            secrets={'webhook_secret': 'whsec-1', 'admin_api_key': 'adm-2'},
            metadata={'verified_owner': True},
        )
    )
    assert status.connected is True
    assert status.onboarding_ready is True
    assert 'website.site.webhook_secret' in status.secret_fields_bound
    record = registry.get('tenant-a', 'my-site')
    assert record is not None
    assert record.channel_kind == 'website'
    assert 'region:eu-west-1' in record.persistent_surfaces
