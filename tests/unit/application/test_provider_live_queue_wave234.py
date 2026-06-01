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
            persistent_surfaces=('evidence',)
            ready=True
        return _R()


def _service(tmp_path):
    docs=FileDistributedDocumentStore(tmp_path/'docs')
    return ProviderAdminService(onboarding_service=_Onboarding(), secret_vault=InMemorySecretVault(), connector_secret_scope=ConnectorSecretScope(), activation_store=FileProviderActivationStore(docs))


def test_provider_live_client_description_exists(tmp_path):
    service=_service(tmp_path)
    view=service.describe_provider_live_client(provider_key='telegram_bot')
    assert view['network_capable'] is True
    assert 'queue_dispatch_endpoint' in view


def test_provider_sync_can_be_queued_and_listed(tmp_path):
    service=_service(tmp_path)
    service.activate_provider(ProviderCredentialSubmission(tenant_id='tenant-a', business_id='biz-a', provider_key='telegram_bot', ownership_key='owner:biz-a', requested_by='tester', external_ref='bot://biz-a', metadata={'verified_owner': True}, secrets={'bot_token': '123:abc'}))
    queued=service.enqueue_provider_sync(tenant_id='tenant-a', business_id='biz-a', provider_key='telegram_bot', operation='communications_write', mode='dry_run', payload={'message': 'hi'})
    assert queued['queued'] is True
    jobs=service.list_provider_queue_jobs(tenant_id='tenant-a', provider_key='telegram_bot')
    assert any(job['payload']['provider_key']=='telegram_bot' for job in jobs)


def test_provider_sync_queue_tick_runs_jobs(tmp_path):
    service=_service(tmp_path)
    service.activate_provider(ProviderCredentialSubmission(tenant_id='tenant-a', business_id='biz-a', provider_key='telegram_bot', ownership_key='owner:biz-a', requested_by='tester', external_ref='bot://biz-a', metadata={'verified_owner': True}, secrets={'bot_token': '123:abc'}))
    service.enqueue_provider_sync(tenant_id='tenant-a', business_id='biz-a', provider_key='telegram_bot', operation='communications_write', mode='dry_run', payload={'message': 'hi'})
    report=service.tick_provider_sync_queue(tenant_id='tenant-a')
    assert report['claimed'] >= 1
