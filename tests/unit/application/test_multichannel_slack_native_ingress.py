from __future__ import annotations

import hashlib
import hmac
import time

import pytest

from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_payload_normalizers import ProviderPayloadNormalizers
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault


def _put(vault: InMemorySecretVault, *, value: str) -> None:
    provider = provider_map()['slack_messaging']
    ref = SecretRef(
        tenant_id='tenant-a',
        connector_id=provider.connector_id,
        scope='business-a',
        secret_name=f'{provider.connector_id}.webhook_secret',
    )
    vault.put(
        SecretRecord(ref=ref, ciphertext=b'pending', source=SecretSource.CONNECTOR),
        plaintext=value.encode(),
    )


def _signature(*, secret: str, timestamp: str, body: bytes) -> str:
    base = b'v0:' + timestamp.encode('ascii') + b':' + body
    return 'v0=' + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()


def test_slack_native_v0_signature_is_verified_fail_closed() -> None:
    provider = provider_map()['slack_messaging']
    vault = InMemorySecretVault()
    _put(vault, value='slack-signing-secret')
    runtime = ProviderWebhookRuntime(vault)
    body = b'{"type":"event_callback","team_id":"T1","event_id":"Ev1","event":{"type":"message","channel":"C1","user":"U1","text":"hello","client_msg_id":"m1"}}'
    timestamp = str(int(time.time()))
    headers = {
        'X-Slack-Request-Timestamp': timestamp,
        'X-Slack-Signature': _signature(secret='slack-signing-secret', timestamp=timestamp, body=body),
    }

    assert runtime.describe(provider).verification_kind == 'slack_hmac_sha256_v0_or_shared_secret'
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers=headers, body=body) is True
    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers=headers, body=body + b' ') is False


def test_slack_native_signature_rejects_stale_requests_even_when_hmac_matches() -> None:
    provider = provider_map()['slack_messaging']
    vault = InMemorySecretVault()
    _put(vault, value='slack-signing-secret')
    runtime = ProviderWebhookRuntime(vault)
    body = b'{"type":"event_callback","event_id":"Ev-old"}'
    timestamp = str(int(time.time()) - 301)
    headers = {
        'X-Slack-Request-Timestamp': timestamp,
        'X-Slack-Signature': _signature(secret='slack-signing-secret', timestamp=timestamp, body=body),
    }

    assert runtime.verify(provider=provider, tenant_id='tenant-a', business_id='business-a', headers=headers, body=body) is False


@pytest.mark.parametrize('timestamp', ['9' * 309, '１２３４５'])
def test_slack_native_signature_rejects_malformed_timestamp_without_raising(timestamp: str) -> None:
    provider = provider_map()['slack_messaging']
    vault = InMemorySecretVault()
    _put(vault, value='slack-signing-secret')
    runtime = ProviderWebhookRuntime(vault)

    assert runtime.verify(
        provider=provider,
        tenant_id='tenant-a',
        business_id='business-a',
        headers={'X-Slack-Request-Timestamp': timestamp, 'X-Slack-Signature': 'v0=untrusted'},
        body=b'{}',
    ) is False


def test_slack_bridge_shared_secret_fallback_remains_supported() -> None:
    provider = provider_map()['slack_messaging']
    vault = InMemorySecretVault()
    _put(vault, value='bridge-secret')
    runtime = ProviderWebhookRuntime(vault)
    body = b'{"event":{"type":"message","channel":"C1","user":"U1","text":"hello"}}'

    assert runtime.verify(
        provider=provider,
        tenant_id='tenant-a',
        business_id='business-a',
        headers={'X-BusinessAIOS-Webhook-Secret': 'bridge-secret'},
        body=body,
    ) is True
    assert runtime.verify(
        provider=provider,
        tenant_id='tenant-a',
        business_id='business-a',
        headers={'X-Slack-Signature': 'v0=bad'},
        body=body,
    ) is False


def test_slack_webhook_normalizer_uses_vendor_event_identity() -> None:
    provider = provider_map()['slack_messaging']
    payload = ProviderPayloadNormalizers().normalize_webhook_payload(
        provider=provider,
        headers={},
        body=b'{"type":"event_callback","team_id":"T1","event_id":"Ev1","event":{"type":"message","channel":"C1","client_msg_id":"m1"}}',
    )

    assert payload == {
        'topic': 'message',
        'source_ref': 'T1',
        'resource_id': 'Ev1',
        'event_key_hint': 'Ev1',
    }
