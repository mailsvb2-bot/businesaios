from application.business_autonomy.provider_catalog import provider_map
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.business_autonomy.provider_inbound_webhook_service import ProviderInboundWebhookService
from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime


class _Processor:
    def __init__(self) -> None:
        self.calls = 0

    def process(self, *, handoff):
        self.calls += 1
        return {'accepted': True, 'decision_envelope': {'decision_id': 'd1'}, 'handoff_seen': bool(handoff)}


def test_provider_inbound_webhook_service_runs_inbound_processor_for_accepted_messaging_webhook(monkeypatch):
    provider = provider_map()['telegram_bot']
    monkeypatch.setattr(ProviderWebhookRuntime, 'verify', lambda self, **kwargs: True)
    runtime = ProviderWebhookRuntime(None)
    processor = _Processor()
    service = ProviderInboundWebhookService(
        webhook_runtime=runtime,
        replay_guard=ProviderWebhookReplayGuard(InMemoryIdempotencyStore()),
        inbound_processor=processor,
    )
    body = b'{"message":{"from":{"id":42},"text":"hello","message_id":9},"update_id":123}'
    out = service.ingest(provider=provider, tenant_id='t1', business_id='b1', headers={}, body=body, event_key='evt-1', topic='telegram_update', owner_id='provider_admin')

    inbound = out.metadata['messaging_inbound_result']
    assert inbound['accepted'] is True
    assert inbound['decision_envelope']['decision_id'] == 'd1'
    replay = service.ingest(provider=provider, tenant_id='t1', business_id='b1', headers={}, body=body, event_key='evt-1', topic='telegram_update', owner_id='provider_admin')
    assert replay.status == 'replayed' and replay.metadata['decision']['resolution'] == 'replay_completed'
    assert processor.calls == 1


def test_provider_inbound_webhook_service_does_not_complete_unprocessed_handoff(monkeypatch):
    provider = provider_map()['telegram_bot']
    monkeypatch.setattr(ProviderWebhookRuntime, 'verify', lambda self, **kwargs: True)
    service = ProviderInboundWebhookService(webhook_runtime=ProviderWebhookRuntime(None), replay_guard=ProviderWebhookReplayGuard(InMemoryIdempotencyStore()))
    body = b'{"message":{"from":{"id":42},"text":"hello","message_id":9},"update_id":123}'
    first = service.ingest(provider=provider, tenant_id='t1', business_id='b1', headers={}, body=body, event_key='evt-unprocessed', topic='telegram_update', owner_id='provider_admin')
    retry = service.ingest(provider=provider, tenant_id='t1', business_id='b1', headers={}, body=body, event_key='evt-unprocessed', topic='telegram_update', owner_id='provider_admin')
    assert first.status == 'accepted' and first.metadata['messaging_handoff'] and not first.metadata['messaging_inbound_result']
    assert retry.status == 'replayed' and retry.metadata['decision']['resolution'] == 'rejected_in_progress'
