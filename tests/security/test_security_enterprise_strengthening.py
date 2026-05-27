from __future__ import annotations

from datetime import datetime, timedelta, timezone

from security import (
    AuditRedactionPolicy,
    ConnectorSecretScope,
    InMemoryKeyProvider,
    KeyPurpose,
    RequestSigner,
    SecretAccessOperation,
    SecretRef,
    SecretScopeBinding,
    SessionPolicy,
    TokenPolicy,
    WebhookSignatureVerifier,
)
from security.secret_contract import SecretRecord, SecretSource, SecretState
from security.secret_vault import InMemorySecretVault


def test_request_signer_binds_timestamp_nonce_and_digest() -> None:
    provider = InMemoryKeyProvider()
    provider.issue_key(key_id='req-v2', purpose=KeyPurpose.REQUEST_SIGNING, tenant_id='t1', connector_id='crm')
    signer = RequestSigner(key_provider=provider, max_age_seconds=60)
    payload = {'amount': 10, 'currency': 'EUR'}
    envelope = signer.sign(payload=payload, tenant_id='t1', connector_id='crm')
    assert envelope.nonce
    assert signer.verify(payload=payload, envelope=envelope) is True
    tampered = type(envelope)(
        key_id=envelope.key_id,
        algorithm=envelope.algorithm,
        signature=envelope.signature,
        signed_at=envelope.signed_at,
        content_digest=envelope.content_digest,
        nonce='tampered',
    )
    assert signer.verify(payload=payload, envelope=tampered) is False


def test_webhook_verifier_rejects_future_timestamp_when_present() -> None:
    provider = InMemoryKeyProvider()
    record = provider.issue_key(key_id='wh-v2', purpose=KeyPurpose.WEBHOOK_VERIFICATION, tenant_id='t1', connector_id='crm')
    verifier = WebhookSignatureVerifier(key_provider=provider, require_timestamp=True, allow_future_skew_seconds=5)
    body = b'{"ok":true}'
    import base64
    import hashlib
    import hmac
    sig = base64.b64encode(hmac.new(record.secret_bytes, body, hashlib.sha256).digest()).decode('ascii')
    future = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()
    result = verifier.verify(
        headers={'X-Signature': sig, 'X-Signature-Timestamp': future, 'X-Key-Id': 'wh-v2'},
        body=body,
        tenant_id='t1',
        connector_id='crm',
    )
    assert result.verified is False
    assert result.reason == 'timestamp_in_future'


def test_token_and_session_policies_cover_enterprise_claims() -> None:
    now = datetime.now(timezone.utc)
    token_verdict = TokenPolicy(required_scopes=('read',), require_issuer=True, require_session_id=True).evaluate(
        issued_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=5),
        now=now,
        scopes=('read',),
        subject='u1',
        audience='api',
        issuer='issuer',
        session_id='session-1',
        token_id='jti-1',
        algorithm='HS256',
    )
    assert token_verdict.allowed is True
    assert token_verdict.labels['session_id'] == 'session-1'
    session_verdict = SessionPolicy(require_mfa=True).evaluate(
        created_at=now - timedelta(minutes=5),
        last_seen_at=now - timedelta(seconds=30),
        now=now,
        auth_level='mfa',
    )
    assert session_verdict.allowed is True


def test_connector_scope_supports_operations_and_prefixes() -> None:
    scope = ConnectorSecretScope(
        (
            SecretScopeBinding(
                tenant_id='t1',
                connector_id='crm',
                allowed_secret_prefixes=('hubspot_',),
                allowed_operations=(SecretAccessOperation.READ, SecretAccessOperation.ROTATE),
            ),
        )
    )
    ref = SecretRef(tenant_id='t1', connector_id='crm', secret_name='hubspot_refresh_token')
    assert scope.is_allowed(ref=ref, connector_id='crm', mode='read') is True
    assert scope.is_allowed(ref=ref, connector_id='crm', mode='rotate') is True
    assert scope.is_allowed(ref=ref, connector_id='crm', mode='delete') is False


def test_secret_vault_tracks_rotation_and_state_and_audit_policy_redacts_metadata() -> None:
    vault = InMemorySecretVault()
    ref = SecretRef(tenant_id='t1', connector_id='crm', secret_name='api_token')
    first = vault.seed_plaintext(ref=ref, plaintext='alpha', source=SecretSource.MEMORY)
    second = vault.seed_plaintext(ref=ref, plaintext='beta', source=SecretSource.MEMORY)
    assert first.state is SecretState.ACTIVE
    assert second.rotated_at is not None
    policy = AuditRedactionPolicy()
    redacted = policy.redact_event_dict({'event_type': 'x', 'metadata': {'email': 'user@example.com', 'token': 'abc'}})
    assert redacted['metadata']['email'] == '<redacted>'
    assert redacted['metadata']['token'] == '***REDACTED***'
