from __future__ import annotations

import hashlib
import json

from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_webhook_route_registry import ProviderWebhookRouteRegistry


def test_generic_multichannel_webhook_event_key_uses_stable_payload_digest() -> None:
    provider = provider_map()['vk_messaging']
    body = json.dumps({'object': {'message': {'from_id': 7, 'text': 'hello', 'id': 9}}}, sort_keys=True).encode()
    row = ProviderWebhookRouteRegistry().extract(provider, {}, body)
    assert row['event_key'] == f"vk_messaging:{hashlib.sha256(body).hexdigest()[:24]}"


def test_vk_native_callback_event_uses_event_id_and_type() -> None:
    provider = provider_map()['vk_messaging']
    body = json.dumps({'type': 'message_new', 'event_id': 'evt-vk-1', 'group_id': 123, 'secret': 'hidden', 'object': {'message': {'from_id': 7, 'peer_id': 7, 'text': 'hello', 'id': 9}}}).encode()
    row = ProviderWebhookRouteRegistry().extract(provider, {}, body)
    assert row['event_key'] == 'evt-vk-1'
    assert row['topic'] == 'message_new'
    assert row['source_ref'] == '123'
