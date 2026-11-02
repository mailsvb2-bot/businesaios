from application.business_autonomy.provider_catalog import provider_map
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.business_autonomy.provider_inbound_webhook_service import ProviderInboundWebhookService
from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime


def test_inbound_webhook_service_emits_messaging_handoff_for_telegram(monkeypatch):
    monkeypatch.setattr(ProviderWebhookRuntime, "verify", lambda self, **kwargs: True)
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


def test_unverified_webhook_cannot_publish_executable_inbound_handoff(monkeypatch):
    # The raw route remains diagnostic, but must never be exposed as an
    # executable DecisionCore handoff before signature verification.
    monkeypatch.setattr(ProviderWebhookRuntime, "verify", lambda self, **kwargs: False)
    service = ProviderInboundWebhookService(
        webhook_runtime=ProviderWebhookRuntime(None),
        replay_guard=ProviderWebhookReplayGuard(InMemoryIdempotencyStore()),
    )
    cases = (
        ("telegram_bot", b'{"update_id":123,"message":{"message_id":9,"text":"hello","chat":{"id":777},"from":{"id":777}}}'),
        ("vk_messaging", b'{"type":"message_new","object":{"message":{"id":9,"from_id":777,"peer_id":777,"text":"hello"}}}'),
        ("max_messaging", b'{"update_id":123,"message":{"message_id":9,"text":"hello","chat":{"id":777},"from":{"id":777}}}'),
    )
    for provider_key, body in cases:
        result = service.ingest(
            provider=provider_map()[provider_key], tenant_id="t1", business_id="b1",
            headers={}, body=body, event_key=f"unverified-{provider_key}",
        )
        assert result.status == "invalid_signature" and not result.accepted
        assert result.metadata["messaging_handoff"] == {}
        assert result.metadata["messaging_inbound_result"] == {}

def test_pending_replay_does_not_expose_executable_handoff_or_ack(monkeypatch):
    monkeypatch.setattr(ProviderWebhookRuntime, "verify", lambda self, **kwargs: True)
    service = ProviderInboundWebhookService(
        webhook_runtime=ProviderWebhookRuntime(None),
        replay_guard=ProviderWebhookReplayGuard(InMemoryIdempotencyStore()),
    )
    request = dict(
        provider=provider_map()["telegram_bot"], tenant_id="t1", business_id="b1",
        headers={}, body=b'{"update_id":123,"message":{"message_id":9,"text":"hello","chat":{"id":777},"from":{"id":777}}}',
        event_key="pending-replay-1",
    )
    first = service.ingest(**request)
    assert first.accepted and first.metadata["messaging_handoff"]
    replay = service.ingest(**request)
    assert replay.status == "replayed" and not replay.accepted
    assert replay.metadata["messaging_handoff"] == {}
    assert replay.metadata["messaging_inbound_result"] == {}
    assert not service.transport_ack_safe(replay)
