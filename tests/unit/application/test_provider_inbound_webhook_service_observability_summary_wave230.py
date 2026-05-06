from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_inbound_webhook_service import ProviderInboundWebhookService
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
from reliability.idempotency_store import InMemoryIdempotencyStore


class _Processor:
    def process(self, *, handoff):
        return {'accepted': True, 'decision_envelope': {'decision_id': 'd1'}}


class _Obs:
    def __init__(self):
        self.calls = []

    def record_webhook(self, **kwargs):
        pass

    def record_webhook_inbound_handoff(self, **kwargs):
        self.calls.append(kwargs)


def test_inbound_webhook_service_emits_inbound_summary_and_observability(monkeypatch):
    provider = provider_map()['telegram_bot']
    monkeypatch.setattr(ProviderWebhookRuntime, 'verify', lambda self, **kwargs: True)
    obs = _Obs()
    service = ProviderInboundWebhookService(
        webhook_runtime=ProviderWebhookRuntime(None),
        replay_guard=ProviderWebhookReplayGuard(InMemoryIdempotencyStore()),
        inbound_processor=_Processor(),
        observability=obs,
    )
    body = b'{"message":{"from":{"id":42},"text":"hello","message_id":9},"update_id":123}'
    out = service.ingest(provider=provider, tenant_id='t1', business_id='b1', headers={}, body=body, event_key='evt-1', topic='telegram_update', owner_id='provider_admin')

    summary = out.metadata['messaging_inbound_summary']
    assert summary['accepted'] is True
    assert summary['decision_id'] == 'd1'
    assert obs.calls[0]['provider_key'] == 'telegram_bot'
    assert obs.calls[0]['inbound_summary']['channel'] == 'telegram'
