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
