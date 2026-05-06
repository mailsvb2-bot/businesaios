from application.business_autonomy.business_connector_framework import ConnectorOnboardingService, StaticTrustOnboarding
from application.business_autonomy.provider_admin_contract import ProviderCredentialSubmission
from application.business_autonomy.provider_admin_service import ProviderAdminService
from application.business_autonomy.distributed_capability_trust_registry import DistributedBusinessRegistry
from runtime.business_autonomy.bootstrap import StaticGovernanceEnablement, StaticPersistenceSurface, _build_typed_channel_registry
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore, FileRegionRouteState
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
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


def test_activation_status_includes_messaging_binding(tmp_path):
    service = _service(tmp_path)
    status = service.activate_provider(
        ProviderCredentialSubmission(
            tenant_id='tenant-a',
            business_id='biz-a',
            provider_key='telegram_bot',
            ownership_key='owner:biz-a',
            requested_by='owner-user',
            external_ref='telegram://biz-a',
            secrets={'bot_token': '123:abc'},
            metadata={'probe_mode': 'dry_run', 'non_ai_mode': 'supervised'},
        )
    )
    binding = dict(status.metadata.get('messaging_binding') or {})
    assert binding.get('channel') == 'telegram'
    assert dict(binding.get('required_capabilities') or {}).get('buttons') is True
