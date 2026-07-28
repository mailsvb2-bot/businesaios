from __future__ import annotations

import base64
import hashlib
import hmac
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from entrypoints.api.request_context import RequestContext
from entrypoints.api.webhook_route_handlers import WebhookRouteHandlers
from security.key_management_contract import KeyPurpose
from security.key_provider import InMemoryKeyProvider
from security.webhook_replay_store import SQLiteWebhookReplayStore, WebhookReplayClaim
from security.webhook_signature_verifier import WEBHOOK_SIGNATURE_VERSION, WebhookSignatureVerifier


class _AllowingWebhookSecurityGuard:
    def enforce(self, **kwargs):
        del kwargs
        return {'allowed': True, 'reason': 'test_security_guard'}


def _signed_headers(*, verifier, key, body: bytes, tenant_id: str, connector_id: str, nonce: str):
    timestamp = datetime.now(UTC).isoformat()
    digest = hashlib.sha256(body).hexdigest()
    payload = verifier.build_signing_payload(
        timestamp=timestamp,
        nonce=nonce,
        tenant_id=tenant_id,
        connector_id=connector_id,
        content_digest=digest,
    )
    signature = base64.b64encode(hmac.new(key.secret_bytes, payload, hashlib.sha256).digest()).decode('ascii')
    return {
        'X-Key-Id': key.key_id,
        'X-Signature': signature,
        'X-Signature-Version': WEBHOOK_SIGNATURE_VERSION,
        'X-Signature-Timestamp': timestamp,
        'X-Signature-Nonce': nonce,
    }


def test_signature_is_bound_to_tenant_and_connector() -> None:
    provider = InMemoryKeyProvider()
    key = provider.issue_key(
        key_id='webhook-tenant-a-connector-a',
        purpose=KeyPurpose.WEBHOOK_VERIFICATION,
        tenant_id='tenant-a',
        connector_id='connector-a',
    )
    verifier = WebhookSignatureVerifier(key_provider=provider)
    body = b'{"event":"created"}'
    headers = _signed_headers(
        verifier=verifier,
        key=key,
        body=body,
        tenant_id='tenant-a',
        connector_id='connector-a',
        nonce='nonce-0000000001',
    )

    accepted = verifier.verify(headers=headers, body=body, tenant_id='tenant-a', connector_id='connector-a')
    wrong_tenant = verifier.verify(headers=headers, body=body, tenant_id='tenant-b', connector_id='connector-a')
    wrong_connector = verifier.verify(headers=headers, body=body, tenant_id='tenant-a', connector_id='connector-b')

    assert accepted.verified is True
    assert wrong_tenant.reason == 'key_scope_mismatch'
    assert wrong_connector.reason == 'key_scope_mismatch'


def test_replay_claim_is_atomic_across_store_instances(tmp_path) -> None:
    path = tmp_path / 'webhook-replay.sqlite3'
    stores = [SQLiteWebhookReplayStore(path) for _ in range(8)]
    claim = WebhookReplayClaim(
        tenant_id='tenant-a',
        connector_id='connector-a',
        nonce='nonce-0000000001',
        signature_timestamp=datetime.now(UTC).isoformat(),
        content_digest='digest-a',
    )

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda store: store.claim(claim), stores))

    assert outcomes.count(True) == 1
    assert outcomes.count(False) == 7


def test_route_rejects_second_delivery_of_valid_signed_webhook(tmp_path) -> None:
    provider = InMemoryKeyProvider()
    key = provider.issue_key(
        key_id='webhook-tenant-a-connector-a',
        purpose=KeyPurpose.WEBHOOK_VERIFICATION,
        tenant_id='tenant-a',
        connector_id='connector-a',
    )
    verifier = WebhookSignatureVerifier(key_provider=provider)
    replay_store = SQLiteWebhookReplayStore(tmp_path / 'webhook-replay.sqlite3')
    handlers = WebhookRouteHandlers(
        verifier=verifier,
        security_guard=_AllowingWebhookSecurityGuard(),
        replay_store=replay_store,
    )
    body = b'{"event":"created"}'
    headers = _signed_headers(
        verifier=verifier,
        key=key,
        body=body,
        tenant_id='tenant-a',
        connector_id='connector-a',
        nonce='nonce-0000000001',
    )
    context = RequestContext(
        tenant_id='tenant-a',
        metadata={'transport_encrypted': True},
    )

    first = handlers.receive(
        headers=headers,
        body=body,
        tenant_id='tenant-a',
        connector_id='connector-a',
        request_context=context,
    )
    second = handlers.receive(
        headers=headers,
        body=body,
        tenant_id='tenant-a',
        connector_id='connector-a',
        request_context=context,
    )

    assert first['accepted'] is True
    assert second['accepted'] is False
    assert second['reason'] == 'webhook_replay_detected'
