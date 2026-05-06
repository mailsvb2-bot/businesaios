from __future__ import annotations

from datetime import timedelta

from security.key_management_contract import KeyPurpose, utc_now
from security.key_provider import InMemoryKeyProvider
from security.key_rotation_journal import SQLiteKeyRotationJournal
from security.key_rotation_policy import KeyRotationPolicy
from security.reencryption_orchestrator import ReencryptionOrchestrator
from security.request_signature_verifier import RequestSignatureVerifier
from security.request_signing import RequestSigner
from security.security_approval_gate import SecurityApprovalGate
from security.security_audit_chain import SQLiteSecurityAuditChain
from security.security_audit_event_store import SQLiteSecurityAuditEventStore
from security.signed_operator_approval import SignedOperatorApprovalStore
from security.tenant_secret_access_policy import TenantSecretAccessPolicy
from security.tenant_secret_scope import TenantSecretScope


def test_request_signature_verifier_round_trip() -> None:
    provider = InMemoryKeyProvider()
    signer = RequestSigner(key_provider=provider)
    verifier = RequestSignatureVerifier(signer=signer)
    payload = {'tenant_id': 't1', 'goal': 'ship'}
    envelope = signer.sign(payload=payload, tenant_id='t1')
    verdict = verifier.verify(payload=payload, envelope=envelope)
    assert verdict.valid is True
    assert verdict.reason == 'ok'


def test_security_audit_event_store_and_chain(tmp_path) -> None:
    event_store = SQLiteSecurityAuditEventStore(str(tmp_path / 'audit.sqlite3'))
    chain = SQLiteSecurityAuditChain(str(tmp_path / 'audit_chain.sqlite3'))
    event_store.append(event_kind='security.login.blocked', payload={'tenant_id': 't1'})
    chain.append(event_kind='security.login.blocked', payload={'tenant_id': 't1'})
    latest = event_store.latest(limit=1)
    assert latest[0]['event_kind'] == 'security.login.blocked'
    assert chain.verify_chain()['ok'] is True


def test_tenant_secret_scope_and_access_policy() -> None:
    scope_builder = TenantSecretScope()
    scope = scope_builder.build_scope(tenant_id='tenant-a', local_scope='crm')
    policy = TenantSecretAccessPolicy()
    assert policy.evaluate(requester_tenant_id='tenant-a', secret_scope=scope).allowed is True
    assert policy.evaluate(requester_tenant_id='tenant-b', secret_scope=scope).allowed is False


def test_key_rotation_policy_and_reencryption(tmp_path) -> None:
    provider = InMemoryKeyProvider()
    current = provider.issue_key(key_id='secret-key-v1', purpose=KeyPurpose.SECRET_ENCRYPTION)
    verdict = KeyRotationPolicy(max_age_days=90).evaluate(created_at=current.created_at - timedelta(days=91), now=utc_now())
    assert verdict.should_rotate is True

    journal = SQLiteKeyRotationJournal(str(tmp_path / 'rotation.sqlite3'))
    report = ReencryptionOrchestrator(key_provider=provider, rotation_journal=journal).rotate_secret_encryption_key(
        current_key_id='secret-key-v1',
        new_key_id='secret-key-v2',
    )
    assert report.success is True
    assert report.new_key_id == 'secret-key-v2'
    assert journal.latest(limit=1)[0]['key_id'] == 'secret-key-v1'


def test_security_approval_gate_and_signed_approval(tmp_path) -> None:
    gate = SecurityApprovalGate()
    verdict = gate.evaluate(operation_kind='key_rotate')
    assert verdict.requires_signed_approval is True

    store = SignedOperatorApprovalStore(str(tmp_path / 'approvals.sqlite3'), 'secret')
    store.grant(
        approval_id='approval-1',
        operation_kind='key_rotate',
        actor='operator',
        payload={'key_id': 'secret-key-v1'},
    )
    verified = store.verify(approval_id='approval-1')
    assert verified['ok'] is True
