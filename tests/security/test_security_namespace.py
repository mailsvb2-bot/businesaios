from __future__ import annotations

from datetime import UTC, datetime, timedelta

from infrastructure.observability.redaction import redact_dict
from infrastructure.secrets.runtime import get_secret, register_runtime_secret
from security import (
    AuditRedactionPolicy,
    ConnectorSecretScope,
    CredentialHandle,
    CredentialManager,
    EncryptionPolicy,
    InMemoryKeyProvider,
    InMemorySecretVault,
    KeyPurpose,
    PayloadRedactor,
    PIIRedactionPolicy,
    RequestSigner,
    SandboxExecutionPolicy,
    SecretRef,
    SecretScopeBinding,
    SessionPolicy,
    TokenPolicy,
    WebhookSignatureVerifier,
)


def test_payload_redactor_masks_secret_keys_and_pii() -> None:
    redactor = PayloadRedactor(pii_policy=PIIRedactionPolicy())
    payload = {'email': 'user@example.com', 'token': 'abc', 'nested': {'phone': '+31 612345678'}}
    redacted = redactor.redact(payload)
    assert redacted['email'] == '<redacted>'
    assert redacted['token'] == '***REDACTED***'
    assert redacted['nested']['phone'] == '<redacted>'


def test_audit_redaction_policy_drops_unknown_fields() -> None:
    policy = AuditRedactionPolicy()
    redacted = policy.redact_event_dict({'event_type': 'x', 'payload': {'password': 'secret'}, 'junk': 1})
    assert 'junk' not in redacted
    assert redacted['payload']['password'] == '***REDACTED***'


def test_secret_vault_roundtrip_and_credential_scope() -> None:
    vault = InMemorySecretVault(policy=EncryptionPolicy())
    ref = SecretRef(tenant_id='t1', connector_id='crm', secret_name='api_token')
    vault.seed_plaintext(ref=ref, plaintext='hello')
    scope = ConnectorSecretScope((SecretScopeBinding(tenant_id='t1', connector_id='crm', allowed_secret_names=('api_token',)),))
    manager = CredentialManager(vault=vault, connector_scope=scope)
    handle = CredentialHandle(ref=ref, connector_id='crm', created_at=datetime.now(UTC))
    assert manager.resolve(handle) == 'hello'


def test_request_signer_and_webhook_verifier() -> None:
    provider = InMemoryKeyProvider()
    provider.issue_key(key_id='req1', purpose=KeyPurpose.REQUEST_SIGNING, tenant_id='t1', connector_id='crm')
    signer = RequestSigner(key_provider=provider)
    payload = {'a': 1}
    envelope = signer.sign(payload=payload, tenant_id='t1', connector_id='crm')
    assert signer.verify(payload=payload, envelope=envelope) is True

    provider.issue_key(key_id='wh1', purpose=KeyPurpose.WEBHOOK_VERIFICATION, tenant_id='t1', connector_id='crm')
    verifier = WebhookSignatureVerifier(key_provider=provider)
    body = b'{"ok":true}'
    key = provider.get_active_for(purpose=KeyPurpose.WEBHOOK_VERIFICATION, tenant_id='t1', connector_id='crm')
    import base64
    import hashlib
    import hmac
    sig = base64.b64encode(hmac.new(key.secret_bytes, body, hashlib.sha256).digest()).decode('ascii')
    result = verifier.verify(headers={'X-Signature': sig}, body=body, tenant_id='t1', connector_id='crm')
    assert result.verified is True


def test_session_token_and_sandbox_policies() -> None:
    now = datetime.now(UTC)
    session_verdict = SessionPolicy().evaluate(created_at=now - timedelta(minutes=10), last_seen_at=now - timedelta(minutes=1), now=now)
    assert session_verdict.allowed is True
    token_verdict = TokenPolicy(required_scopes=('read',)).evaluate(
        issued_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(minutes=5),
        now=now,
        scopes=('read',),
        subject='u1',
        audience='api',
    )
    assert token_verdict.allowed is True
    sandbox_verdict = SandboxExecutionPolicy().evaluate(requested_modules=('math', 'json'), requests_network=False, requests_filesystem_write=False)
    assert sandbox_verdict.allowed is True


def test_runtime_secret_adapter_keeps_historical_entrypoint() -> None:
    register_runtime_secret('TEST_RUNTIME_SECRET', 'value')
    assert get_secret('TEST_RUNTIME_SECRET') == 'value'


def test_infrastructure_redact_dict_uses_security_namespace() -> None:
    redacted = redact_dict({'payload': {'authorization': 'Bearer abc', 'email': 'user@example.com'}})
    assert redacted['payload']['authorization'] == '***REDACTED***'
    assert redacted['payload']['email'] == '<redacted>'
