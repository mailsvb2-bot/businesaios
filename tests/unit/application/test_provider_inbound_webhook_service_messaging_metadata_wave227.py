from __future__ import annotations

from application.business_autonomy.provider_catalog import provider_map
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.business_autonomy.provider_inbound_webhook_service import ProviderInboundWebhookService
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
from security.secret_vault import InMemorySecretVault


def test_inbound_webhook_service_returns_route_with_messaging_ingress_for_telegram():
    service = ProviderInboundWebhookService(
        webhook_runtime=ProviderWebhookRuntime(secret_vault=InMemorySecretVault()),
        replay_guard=ProviderWebhookReplayGuard(idempotency_store=InMemoryIdempotencyStore()),
    )
    provider = provider_map()['telegram_bot']
    body = b'{"update_id":123,"message":{"message_id":456,"text":"hello","chat":{"id":999},"from":{"id":777}}}'
    result = service.ingest(provider=provider, tenant_id='t1', business_id='b1', headers={}, body=body, event_key='evt-1', topic='telegram_update')
    route = dict(result.metadata or {}).get('route', {})
    assert route['messaging_ingress']['channel'] == 'telegram'
    assert route['messaging_ingress']['correlation_id'] == '123'
