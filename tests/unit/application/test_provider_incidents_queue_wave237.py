from __future__ import annotations

from application.business_autonomy.business_connector_framework import ConnectorOnboardingService
from application.business_autonomy.provider_admin_contract import ProviderCredentialSubmission
from application.business_autonomy.provider_admin_service import ProviderAdminService
from application.business_autonomy.provider_runtime_contract import ProviderSyncRunResult
from application.business_autonomy.provider_catalog import provider_map
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
from runtime.business_autonomy.provider_inbound_webhook_service import ProviderInboundWebhookService
from runtime.business_autonomy.provider_live_probe_runtime import ProviderLiveProbeRuntime
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.business_autonomy.provider_queue_execution import ProviderQueueExecutionRuntime
from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from runtime.queue.job_store_sqlite import SqliteJobStore
from security.connector_secret_scope import ConnectorSecretScope
from security.secret_vault import InMemorySecretVault


class _DummyOnboarding(ConnectorOnboardingService):
    def __init__(self):
        pass
    def onboard(self, request):
        class _R:
            persistent_surfaces = ('provider:test',)
            ready = True
        return _R()


def _service(tmp_path):
    vault = InMemorySecretVault()
    scope = ConnectorSecretScope()
    store = FileProviderActivationStore(documents=FileDistributedDocumentStore(tmp_path / 'activation'))
    return ProviderAdminService(onboarding_service=_DummyOnboarding(), secret_vault=vault, connector_secret_scope=scope, activation_store=store)


def _activate(service: ProviderAdminService, provider_key: str, tmp_path):
    provider = provider_map()[provider_key]
    secrets = {field.field_key: 'token-123' for field in provider.secret_fields if field.required}
    if not secrets:
        secrets = {field.field_key: 'x' for field in provider.secret_fields[:1]}
    submission = ProviderCredentialSubmission(tenant_id='tenant-a', business_id='biz-a', provider_key=provider_key, ownership_key='owner-1', requested_by='tester', external_ref='ext', region='eu-west-1', metadata={}, secrets=secrets)
    return service.activate_provider(submission)


class _RetryRuntime:
    def __init__(self) -> None:
        self.attempts = []

    def run(self, *, provider, operation, mode, attempts=1, **_kwargs):
        self.attempts.append(attempts)
        delay = 30 * (2 ** max(0, attempts - 1))
        return ProviderSyncRunResult(provider_key=provider.provider_key, operation=operation, mode=mode, status='live_execution_failed', accepted=False, metadata={'retry_policy': {'category': 'rate_limit', 'retryable': True, 'next_delay_seconds': delay, 'max_attempts': 6}})


def test_sync_failure_records_incident_and_queue_metrics(tmp_path):
    service = _service(tmp_path)
    _activate(service, 'telegram_bot', tmp_path)
    provider = provider_map()['telegram_bot']
    runtime = ProviderLiveSyncRuntime(service.secret_vault, transports={})
    result = runtime.run(provider=provider, tenant_id='tenant-a', business_id='biz-a', operation='message_read', mode='live', payload={})
    assert result.status == 'live_transport_unbound'
    incidents = service.list_provider_runtime_incidents(tenant_id='tenant-a', business_id='biz-a', provider_key='telegram_bot')
    assert incidents and incidents[0]['kind'] == 'sync'
    queue = ProviderQueueExecutionRuntime(service.secret_vault, live_runtime=runtime)
    queue.enqueue_sync(provider=provider, tenant_id='tenant-a', business_id='biz-a', operation='message_read', mode='dry_run')
    metrics = queue.metrics(tenant_id='tenant-a')
    assert metrics['pending'] >= 1


def test_probe_and_webhook_failures_record_incidents(tmp_path):
    service = _service(tmp_path)
    _activate(service, 'shopify', tmp_path)
    provider = provider_map()['shopify']
    probe = ProviderLiveProbeRuntime(service.secret_vault)
    probe_result = probe.run(provider=provider, tenant_id='tenant-a', business_id='biz-a', mode='live')
    assert probe_result.status in {'probe_prepared_only', 'probe_live_ok', 'probe_live_failed'}
    webhook = ProviderInboundWebhookService(webhook_runtime=ProviderWebhookRuntime(service.secret_vault), replay_guard=ProviderWebhookReplayGuard(idempotency_store=InMemoryIdempotencyStore()))
    ingress = webhook.ingest(provider=provider, tenant_id='tenant-a', business_id='biz-a', headers={}, body=b'{}', event_key='evt-1', topic='orders/create')
    assert ingress.status == 'invalid_signature'
    incidents = service.list_provider_runtime_incidents(tenant_id='tenant-a', business_id='biz-a', provider_key='shopify')
    statuses = {row['status'] for row in incidents}
    assert 'invalid_signature' in statuses


def test_max_queue_owns_retry_attempts_and_backoff(tmp_path):
    provider = provider_map()['max_messaging']
    runtime = _RetryRuntime()
    queue = ProviderQueueExecutionRuntime(InMemorySecretVault(), live_runtime=runtime, store=SqliteJobStore(tmp_path / 'provider-queue.sqlite3'))
    dispatched = queue.enqueue_sync(provider=provider, tenant_id='tenant-a', business_id='biz-a', operation='message_read', mode='live', payload={'chat_id': '1'})
    report = queue.tick(provider_registry={'max_messaging': provider}, tenant_id='tenant-a')
    stored = queue.store.get(tenant_id='tenant-a', job_id=dispatched.job_id)
    assert report['retried'] == 1 and runtime.attempts == [1]
    assert stored is not None and stored.attempts == 1 and stored.max_attempts == 6 and stored.state.value == 'pending'
    retry_delay = (stored.run_at - stored.updated_at).total_seconds()
    assert 29 <= retry_delay <= 31
    replay = queue._runner({'max_messaging': provider})(stored.__class__(**{**stored.__dict__, 'attempts': 3}))
    assert runtime.attempts[-1] == 3 and replay.retry_delay_seconds == 120
