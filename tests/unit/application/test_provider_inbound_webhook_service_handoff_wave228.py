from application.business_autonomy.provider_catalog import provider_map
from infra.idempotency_store import InMemoryIdempotencyStore
from runtime.business_autonomy.provider_inbound_webhook_service import ProviderInboundWebhookService
from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime


def test_inbound_webhook_service_emits_messaging_handoff_for_telegram():
    service = ProviderInboundWebhookService(
        webhook_runtime=ProviderWebhookRuntime(None),
        replay_guard=ProviderWebhookReplayGuard(InMemoryIdempotencyStore()),
    )
    provider = provider_map()['telegram_bot']
    body = b'{"update_id":123,"message":{"message_id":9,"text":"hello","chat":{"id":777},"from":{"id":777}}}'
    out = service.ingest(
        provider=provider,
        tenant_id='t1',
        business_id='b1',
        headers={},
        body=body,
        event_key='e1',
        topic='',
        owner_id='provider_admin',
    )
    handoff = dict(out.metadata).get('messaging_handoff') or {}
    assert handoff['inbound_message']['channel'] == 'telegram'
    assert handoff['world_state_input']['transport_message_id'] == '9'
