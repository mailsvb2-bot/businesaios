from __future__ import annotations

from pathlib import Path

from security.kms_provider_inmemory import InMemoryKMSProvider
from security.kms_provider_registry import KMSProviderRegistry
from security.security_approval_gate import SecurityApprovalGate
from security.security_audit_chain import SQLiteSecurityAuditChain
from security.security_governance_orchestrator import SecurityGovernanceOrchestrator
from security.security_incident_registry import SQLiteSecurityIncidentRegistry
from security.security_quarantine_registry import SQLiteSecurityQuarantineRegistry
from security.signed_operator_approval import SignedOperatorApprovalStore
from security.token_revocation_store import SQLiteTokenRevocationStore


def test_security_governance_high_risk_requires_signed_approval(tmp_path: Path) -> None:
    approvals = SignedOperatorApprovalStore(str(tmp_path / 'approvals.sqlite3'), 'secret')
    approvals.grant(
        approval_id='a1',
        operation_kind='key_rotate',
        actor='tester',
        payload={'ticket': 'SEC-1'},
    )
    orchestrator = SecurityGovernanceOrchestrator(
        approval_gate=SecurityApprovalGate(),
        approval_store=approvals,
        incident_registry=SQLiteSecurityIncidentRegistry(str(tmp_path / 'incidents.sqlite3')),
        revocation_store=SQLiteTokenRevocationStore(str(tmp_path / 'revoked.sqlite3')),
        quarantine_registry=SQLiteSecurityQuarantineRegistry(str(tmp_path / 'quarantine.sqlite3')),
        audit_chain=SQLiteSecurityAuditChain(str(tmp_path / 'audit_chain.sqlite3')),
    )
    report = orchestrator.execute_high_risk_operation(
        operation_kind='key_rotate',
        actor='tester',
        approval_id='a1',
        payload={'target': 'key-1'},
    )
    assert report.success is True


def test_security_governance_quarantines_compromised_token(tmp_path: Path) -> None:
    revoked = SQLiteTokenRevocationStore(str(tmp_path / 'revoked.sqlite3'))
    quarantine = SQLiteSecurityQuarantineRegistry(str(tmp_path / 'quarantine.sqlite3'))
    orchestrator = SecurityGovernanceOrchestrator(
        approval_gate=SecurityApprovalGate(),
        approval_store=SignedOperatorApprovalStore(str(tmp_path / 'approvals.sqlite3'), 'secret'),
        incident_registry=SQLiteSecurityIncidentRegistry(str(tmp_path / 'incidents.sqlite3')),
        revocation_store=revoked,
        quarantine_registry=quarantine,
        audit_chain=SQLiteSecurityAuditChain(str(tmp_path / 'audit_chain.sqlite3')),
    )
    report = orchestrator.quarantine_compromised_token(
        token_fingerprint='fp-1',
        actor='tester',
        reason='suspected compromise',
    )
    assert report.success is True
    assert revoked.is_revoked(token_fingerprint='fp-1') is True
    assert quarantine.is_quarantined(entity_kind='token', entity_id='fp-1') is True


def test_kms_registry_accepts_inmemory_provider() -> None:
    registry = KMSProviderRegistry()
    provider = InMemoryKMSProvider()
    entry = registry.register(provider)
    handle = provider.create_key(key_id='k1', algorithm='AES-256-GCM')
    active = registry.get(entry.provider_name).get_active_key(key_id='k1')
    assert active.key_id == handle.key_id
    assert active.key_version == 1
