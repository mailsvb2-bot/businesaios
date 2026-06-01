from __future__ import annotations

from application.business_autonomy.provider_admin_contract import ProviderCredentialSubmission
from application.business_autonomy.provider_admin_service import ProviderAdminService
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
from security.connector_secret_scope import ConnectorSecretScope
from security.secret_vault import InMemorySecretVault


class _Onboarding:
    def onboard(self, request):
        class _R:
            persistent_surfaces = ('evidence',)
            ready = True
        return _R()


def _service(tmp_path):
    docs = FileDistributedDocumentStore(tmp_path / 'docs')
    return ProviderAdminService(
        onboarding_service=_Onboarding(),
        secret_vault=InMemorySecretVault(),
        connector_secret_scope=ConnectorSecretScope(),
        activation_store=FileProviderActivationStore(docs),
    )


def test_provider_live_probe_returns_prepared_state(tmp_path):
    service = _service(tmp_path)
    service.activate_provider(ProviderCredentialSubmission(
        tenant_id='tenant-a',
        business_id='shop-a',
        provider_key='shopify',
        ownership_key='owner:shop-a',
        requested_by='tester',
        external_ref='shop://a',
        metadata={'verified_owner': True},
        secrets={'admin_access_token': 'token', 'webhook_secret': 'whsec'},
    ))
    result = service.probe_provider_live(tenant_id='tenant-a', business_id='shop-a', provider_key='shopify', mode='dry_run')
    assert result['status'] == 'probe_prepared_only'
    assert result['metadata']['response']['network_capable'] is True


def test_provider_pagination_walk_persists_history(tmp_path):
    service = _service(tmp_path)
    service.activate_provider(ProviderCredentialSubmission(
        tenant_id='tenant-a',
        business_id='hub-a',
        provider_key='hubspot',
        ownership_key='owner:hub-a',
        requested_by='tester',
        external_ref='hub://a',
        metadata={'verified_owner': True},
        secrets={'private_app_token': 'token'},
    ))
    result = service.paginate_provider_sync(
        tenant_id='tenant-a',
        business_id='hub-a',
        provider_key='hubspot',
        operation='contact_sync',
        mode='dry_run',
        payload={'cursor': 'cursor-1'},
        max_pages=2,
    )
    assert result['status'] == 'pagination_walk_complete'
    assert result['metadata']['page_count'] >= 1
    history = service.list_provider_sync_history(tenant_id='tenant-a', business_id='hub-a', provider_key='hubspot')
    assert history
