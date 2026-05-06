from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_inbound_webhook_service import ProviderInboundWebhookService
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
from reliability.idempotency_store import InMemoryIdempotencyStore


class _Processor:
    def process(self, *, handoff):
        return {'accepted': True, 'decision_envelope': {'decision_id': 'd1'}, 'handoff_seen': bool(handoff)}


def test_provider_inbound_webhook_service_runs_inbound_processor_for_accepted_messaging_webhook(monkeypatch):
    provider = provider_map()['telegram_bot']
    monkeypatch.setattr(ProviderWebhookRuntime, 'verify', lambda self, **kwargs: True)
    runtime = ProviderWebhookRuntime(None)
    service = ProviderInboundWebhookService(
        webhook_runtime=runtime,
        replay_guard=ProviderWebhookReplayGuard(InMemoryIdempotencyStore()),
        inbound_processor=_Processor(),
    )
    body = b'{"message":{"from":{"id":42},"text":"hello","message_id":9},"update_id":123}'
    out = service.ingest(provider=provider, tenant_id='t1', business_id='b1', headers={}, body=body, event_key='evt-1', topic='telegram_update', owner_id='provider_admin')

    inbound = out.metadata['messaging_inbound_result']
    assert inbound['accepted'] is True
    assert inbound['decision_envelope']['decision_id'] == 'd1'
