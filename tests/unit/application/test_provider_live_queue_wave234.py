from __future__ import annotations

from application.business_autonomy.provider_admin_contract import ProviderCredentialSubmission
from application.business_autonomy.provider_admin_service import ProviderAdminService
from application.business_autonomy.provider_catalog import provider_map
from application.business_autonomy.provider_runtime_contract import ProviderSyncRunResult
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
from runtime.business_autonomy.provider_queue_execution import ProviderQueueExecutionRuntime, _queue_store_path
from runtime.queue.job_contract import JobState
from runtime.queue.job_store_sqlite import SqliteJobStore
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
    queued=service.enqueue_provider_sync(tenant_id='tenant-a', business_id='biz-a', provider_key='telegram_bot', operation='communications_write', mode='dry_run', payload={'message': 'hi'})
    report=service.tick_provider_sync_queue(tenant_id='tenant-a', worker_id='provider-route-worker')
    assert report['claimed'] >= 1
    assert report['worker_id'] == 'provider-route-worker'
    history=service.list_provider_sync_history(tenant_id='tenant-a', business_id='biz-a', provider_key='telegram_bot', limit=100)
    assert any(row.get('queue_job_id') == queued['job_id'] for row in history)


def test_provider_queue_uses_shared_data_dir(tmp_path, monkeypatch):
    shared = tmp_path / 'shared-runtime'
    monkeypatch.setenv('DATA_DIR', str(shared))
    assert _queue_store_path() == shared / 'runtime' / 'queue' / 'provider_sync_jobs.sqlite3'


def test_targeted_provider_queue_tick_never_executes_unrelated_due_jobs(tmp_path):
    class _LiveRuntime:
        def __init__(self):
            self.calls = []
        def run(self, **kwargs):
            self.calls.append(kwargs)
            return ProviderSyncRunResult(provider_key=kwargs['provider'].provider_key, operation=kwargs['operation'], mode=kwargs['mode'], status='live_executed', accepted=True, metadata={})

    live = _LiveRuntime()
    store = SqliteJobStore(tmp_path / 'provider-jobs.sqlite3')
    queue = ProviderQueueExecutionRuntime(InMemorySecretVault(), live_runtime=live, store=store)
    provider = provider_map()['telegram_bot']
    target = queue.enqueue_sync(provider=provider, tenant_id='tenant-a', business_id='biz-target', operation='communications_write', mode='dry_run', payload={'message': 'target'})
    unrelated = queue.enqueue_sync(provider=provider, tenant_id='tenant-a', business_id='biz-other', operation='communications_write', mode='dry_run', payload={'message': 'other'})

    report = queue.tick(provider_registry={'telegram_bot': provider}, tenant_id='tenant-a', worker_id='provider-targeted-test', job_id=target.job_id)

    assert report['succeeded'] == 1 and report['claimed'] == 1
    assert [call['business_id'] for call in live.calls] == ['biz-target']
    assert store.get(tenant_id='tenant-a', job_id=target.job_id).state is JobState.SUCCEEDED
    assert store.get(tenant_id='tenant-a', job_id=unrelated.job_id).state is JobState.PENDING
