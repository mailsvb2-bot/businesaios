from __future__ import annotations

import hashlib
import json

from application.business_autonomy.provider_catalog import provider_map
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.business_autonomy.provider_inbound_webhook_service import ProviderInboundWebhookService
from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault


def test_lowercase_http_headers_and_legacy_fallback_use_signed_stable_multichannel_event_key(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    provider = provider_map()['vk_messaging']
    vault = InMemorySecretVault()
    ref = SecretRef(tenant_id='tenant-a', connector_id=provider.connector_id, scope='business-a', secret_name=f'{provider.connector_id}.webhook_secret')
    vault.put(SecretRecord(ref=ref, ciphertext=b'pending', source=SecretSource.CONNECTOR), plaintext=b'secret')
    body = json.dumps({'object': {'message': {'from_id': 7, 'text': 'hello', 'id': 9}}}, sort_keys=True).encode()
    service = ProviderInboundWebhookService(webhook_runtime=ProviderWebhookRuntime(vault), replay_guard=ProviderWebhookReplayGuard(InMemoryIdempotencyStore()))
    result = service.ingest(provider=provider, tenant_id='tenant-a', business_id='business-a', headers={'x-businessaios-webhook-secret': 'secret'}, body=body, event_key='payload-digest-fallback')
    assert result.accepted is True
    assert result.event_key == f"vk_messaging:{hashlib.sha256(body).hexdigest()[:24]}"
