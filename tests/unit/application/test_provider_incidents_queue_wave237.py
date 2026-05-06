
from __future__ import annotations

from application.business_autonomy.provider_admin_service import ProviderAdminService
from application.business_autonomy.provider_catalog import provider_map
from application.business_autonomy.provider_admin_contract import ProviderCredentialSubmission
from application.business_autonomy.business_connector_framework import ConnectorOnboardingService
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore
from runtime.business_autonomy.provider_inbound_webhook_service import ProviderInboundWebhookService
from runtime.business_autonomy.provider_live_probe_runtime import ProviderLiveProbeRuntime
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.business_autonomy.provider_queue_execution import ProviderQueueExecutionRuntime
from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from security.connector_secret_scope import ConnectorSecretScope
from security.secret_vault import InMemorySecretVault
from reliability.idempotency_store import InMemoryIdempotencyStore


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
    return ProviderAdminService(
        onboarding_service=_DummyOnboarding(),
        secret_vault=vault,
        connector_secret_scope=scope,
        activation_store=store,
    )


def _activate(service: ProviderAdminService, provider_key: str, tmp_path):
    provider = provider_map()[provider_key]
    secrets = {field.field_key: 'token-123' for field in provider.secret_fields if field.required}
    if not secrets:
        secrets = {field.field_key: 'x' for field in provider.secret_fields[:1]}
    submission = ProviderCredentialSubmission(
        tenant_id='tenant-a', business_id='biz-a', provider_key=provider_key, ownership_key='owner-1', requested_by='tester', external_ref='ext', region='eu-west-1', metadata={}, secrets=secrets,
    )
    return service.activate_provider(submission)


def test_sync_failure_records_incident_and_queue_metrics(tmp_path):
    service = _service(tmp_path)
    _activate(service, 'telegram_bot', tmp_path)
    provider = provider_map()['telegram_bot']
    runtime = ProviderLiveSyncRuntime(service.secret_vault, transports={})
    result = runtime.run(provider=provider, tenant_id='tenant-a', business_id='biz-a', operation='message_send', mode='live', payload={})
    assert result.status == 'live_transport_unbound'
    incidents = service.list_provider_runtime_incidents(tenant_id='tenant-a', business_id='biz-a', provider_key='telegram_bot')
    assert incidents and incidents[0]['kind'] == 'sync'
    queue = ProviderQueueExecutionRuntime(service.secret_vault, live_runtime=runtime)
    queue.enqueue_sync(provider=provider, tenant_id='tenant-a', business_id='biz-a', operation='message_send', mode='dry_run')
    metrics = queue.metrics(tenant_id='tenant-a')
    assert metrics['pending'] >= 1


def test_probe_and_webhook_failures_record_incidents(tmp_path):
    service = _service(tmp_path)
    _activate(service, 'shopify', tmp_path)
    provider = provider_map()['shopify']
    probe = ProviderLiveProbeRuntime(service.secret_vault)
    probe_result = probe.run(provider=provider, tenant_id='tenant-a', business_id='biz-a', mode='live')
    assert probe_result.status in {'probe_prepared_only', 'probe_live_ok', 'probe_live_failed'}
    webhook = ProviderInboundWebhookService(
        webhook_runtime=ProviderWebhookRuntime(service.secret_vault),
        replay_guard=ProviderWebhookReplayGuard(idempotency_store=InMemoryIdempotencyStore()),
    )
    ingress = webhook.ingest(provider=provider, tenant_id='tenant-a', business_id='biz-a', headers={}, body=b'{}', event_key='evt-1', topic='orders/create')
    assert ingress.status == 'invalid_signature'
    incidents = service.list_provider_runtime_incidents(tenant_id='tenant-a', business_id='biz-a', provider_key='shopify')
    statuses = {row['status'] for row in incidents}
    assert 'invalid_signature' in statuses
