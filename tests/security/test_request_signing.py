from __future__ import annotations

from datetime import timedelta

from security.key_management_contract import KeyPurpose
from security.key_provider import InMemoryKeyProvider
from security.request_signing import RequestSigner, SignedRequestEnvelope, utc_now


def test_request_signer_roundtrip_accepts_canonical_payload() -> None:
    signer = RequestSigner(key_provider=InMemoryKeyProvider())
    payload = {'amount': 1250, 'currency': 'EUR', 'tenant_id': 'tenant-a'}

    envelope = signer.sign(payload=payload, tenant_id='tenant-a', connector_id='billing')

    assert envelope.algorithm == 'hmac-sha256:v2'
    assert signer.verify(payload=payload, envelope=envelope) is True


def test_request_signer_rejects_tampered_payload() -> None:
    signer = RequestSigner(key_provider=InMemoryKeyProvider())
    envelope = signer.sign(payload={'tenant_id': 'tenant-a', 'operation': 'charge', 'amount': 10}, tenant_id='tenant-a')

    verified = signer.verify(
        payload={'tenant_id': 'tenant-a', 'operation': 'charge', 'amount': 11},
        envelope=envelope,
    )

    assert verified is False


def test_request_signer_rejects_expired_and_future_envelopes() -> None:
    signer = RequestSigner(key_provider=InMemoryKeyProvider(), max_age_seconds=60, allow_future_skew_seconds=5)
    payload = {'tenant_id': 'tenant-a', 'operation': 'sync'}
    fresh = signer.sign(payload=payload, tenant_id='tenant-a')

    stale = SignedRequestEnvelope(
        key_id=fresh.key_id,
        algorithm=fresh.algorithm,
        signature=fresh.signature,
        signed_at=fresh.signed_at - timedelta(minutes=5),
        content_digest=fresh.content_digest,
        nonce=fresh.nonce,
    )
    too_future = SignedRequestEnvelope(
        key_id=fresh.key_id,
        algorithm=fresh.algorithm,
        signature=fresh.signature,
        signed_at=utc_now() + timedelta(minutes=5),
        content_digest=fresh.content_digest,
        nonce=fresh.nonce,
    )

    assert signer.verify(payload=payload, envelope=stale, now=utc_now()) is False
    assert signer.verify(payload=payload, envelope=too_future, now=utc_now()) is False


def test_request_signer_is_order_invariant_for_json_mappings() -> None:
    signer = RequestSigner(key_provider=InMemoryKeyProvider())
    payload_a = {'tenant_id': 'tenant-a', 'amount': 5, 'currency': 'EUR'}
    payload_b = {'currency': 'EUR', 'amount': 5, 'tenant_id': 'tenant-a'}

    envelope = signer.sign(payload=payload_a, tenant_id='tenant-a')

    assert signer.verify(payload=payload_b, envelope=envelope) is True


def test_request_signer_rejects_wrong_key_purpose_even_if_signature_shape_is_valid() -> None:
    key_provider = InMemoryKeyProvider()
    wrong = key_provider.issue_key(key_id='wrong-purpose', purpose=KeyPurpose.SECRET_ENCRYPTION, tenant_id='tenant-a')
    signer = RequestSigner(key_provider=key_provider)
    payload = {'tenant_id': 'tenant-a', 'operation': 'sync'}

    envelope = SignedRequestEnvelope(
        key_id=wrong.key_id,
        algorithm='hmac-sha256:v2',
        signature='not-used',
        signed_at=utc_now(),
        content_digest='abcd',
        nonce='nonce',
    )

    assert signer.verify(payload=payload, envelope=envelope) is False


def test_request_signer_accepts_legacy_v1_envelope_for_backward_compat() -> None:
    key_provider = InMemoryKeyProvider()
    signer = RequestSigner(key_provider=key_provider)
    payload = {'tenant_id': 'tenant-a', 'operation': 'sync'}
    modern = signer.sign(payload=payload, tenant_id='tenant-a')
    key = key_provider.get(modern.key_id)

    import base64
    import hashlib
    import hmac

    legacy_signature = base64.b64encode(hmac.new(key.secret_bytes, b'{"operation":"sync","tenant_id":"tenant-a"}', hashlib.sha256).digest()).decode('ascii')
    legacy = SignedRequestEnvelope(
        key_id=modern.key_id,
        algorithm='hmac-sha256:v1',
        signature=legacy_signature,
        signed_at=modern.signed_at,
        content_digest=modern.content_digest,
        nonce=modern.nonce,
    )

    assert signer.verify(payload=payload, envelope=legacy, now=utc_now()) is True
