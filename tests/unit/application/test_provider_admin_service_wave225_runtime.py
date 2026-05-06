from __future__ import annotations

from application.business_autonomy.business_connector_framework import ConnectorOnboardingService, StaticTrustOnboarding
from application.business_autonomy.provider_admin_contract import ProviderCredentialSubmission
from application.business_autonomy.provider_admin_service import ProviderAdminService
from runtime.business_autonomy.bootstrap import StaticGovernanceEnablement, StaticPersistenceSurface, _build_typed_channel_registry
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore, FileRegionRouteState
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
from application.business_autonomy.distributed_capability_trust_registry import DistributedBusinessRegistry
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


def test_platform_infra_activation_records_runtime_probe(tmp_path):
    service = _service(tmp_path)
    status = service.activate_provider(
        ProviderCredentialSubmission(
            tenant_id='tenant-a',
            business_id='runtime-admin',
            provider_key='postgres_runtime',
            ownership_key='owner:runtime-admin',
            requested_by='owner-user',
            external_ref='postgres://cluster/runtime',
            secrets={'dsn': 'postgres://user:pass@localhost:5432/db'},
            metadata={'probe_mode': 'dry_run', 'activate_runtime': True},
        )
    )
    runtime_activation = dict(status.metadata.get('runtime_activation') or {})
    assert runtime_activation.get('runtime_kind') == 'postgres'
    assert runtime_activation.get('health', {}).get('status') == 'ready_for_credentials'
    assert 'runtime:postgres_runtime' in status.persistent_surfaces
