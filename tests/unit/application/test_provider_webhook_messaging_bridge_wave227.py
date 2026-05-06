from __future__ import annotations

from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_webhook_messaging_bridge import resolve_provider_webhook_messaging_ingress
from runtime.business_autonomy.provider_webhook_route_registry import ProviderWebhookRouteRegistry


def test_telegram_webhook_messaging_ingress_is_extracted():
    provider = provider_map()['telegram_bot']
    payload = {'update_id': 123, 'message': {'message_id': 456, 'text': 'hello', 'chat': {'id': 999}, 'from': {'id': 777}}}
    out = resolve_provider_webhook_messaging_ingress(provider=provider, normalized_payload=payload)
    assert out is not None
    assert out.channel == 'telegram'
    assert out.user_id == '777'
    assert out.correlation_id == '123'


def test_whatsapp_webhook_messaging_ingress_is_extracted():
    provider = provider_map()['whatsapp_cloud']
    payload = {'entry': [{'changes': [{'value': {'messages': [{'from': '15550001111', 'id': 'wamid-1', 'text': {'body': 'hi there'}}]}}]}]}
    out = resolve_provider_webhook_messaging_ingress(provider=provider, normalized_payload=payload)
    assert out is not None
    assert out.channel == 'whatsapp'
    assert out.user_id == '15550001111'
    assert out.transport_message_id == 'wamid-1'


def test_webhook_route_registry_includes_messaging_ingress_metadata_for_messaging_webhooks():
    provider = provider_map()['telegram_bot']
    body = b'{"update_id":123,"message":{"message_id":456,"text":"hello","chat":{"id":999},"from":{"id":777}}}'
    out = ProviderWebhookRouteRegistry().extract(provider, {}, body)
    assert out['messaging_ingress']['channel'] == 'telegram'
    assert out['messaging_ingress']['user_id'] == '777'
