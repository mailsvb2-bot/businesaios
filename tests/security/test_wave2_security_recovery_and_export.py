from __future__ import annotations

from pathlib import Path

from security.audit_export_verifier import AuditExportVerifier
from security.audit_redaction_policy import AuditRedactionPolicy
from security.external_audit_export_signer import ExternalAuditExportSigner
from security.key_management_contract import KeyPurpose
from security.key_provider import InMemoryKeyProvider
from security.request_signature_verifier import RequestSignatureVerifier
from security.request_signing import RequestSigner
from security.security_approval_gate import SecurityApprovalGate
from security.security_audit_chain import SQLiteSecurityAuditChain
from security.security_audit_export_service import SecurityAuditExportService
from security.security_governance_orchestrator import SecurityGovernanceOrchestrator
from security.security_incident_drill_history import SQLiteSecurityIncidentDrillHistory
from security.security_incident_recovery_orchestrator import SecurityIncidentRecoveryOrchestrator
from security.security_incident_registry import SQLiteSecurityIncidentRegistry
from security.security_operator_workflow_store import SQLiteSecurityOperatorWorkflowStore
from security.security_quarantine_registry import SQLiteSecurityQuarantineRegistry
from security.signed_operator_approval import SignedOperatorApprovalStore
from security.token_revocation_store import SQLiteTokenRevocationStore


def test_security_audit_export_service_redacts_and_verifies() -> None:
    service = SecurityAuditExportService(
        redaction_policy=AuditRedactionPolicy(),
        signer=ExternalAuditExportSigner('secret'),
        verifier=AuditExportVerifier('secret'),
    )
    signed = service.export_payload(payload={'token': 'abc', 'nested': {'password': 'pw'}})
    assert signed['payload']['token'] == '***REDACTED***'
    assert signed['payload']['nested']['password'] == '***REDACTED***'
    assert service.verify_export(signed_payload=signed) is True


def test_request_signer_round_trip_with_verifier() -> None:
    keys = InMemoryKeyProvider()
    keys.issue_key(key_id='req-sign-1', purpose=KeyPurpose.REQUEST_SIGNING)
    signer = RequestSigner(key_provider=keys)
    payload = {'kind': 'rotate', 'target': 'key-1'}
    envelope = signer.sign(payload=payload)
    assert signer.verify(payload=payload, envelope=envelope) is True
    verifier = RequestSignatureVerifier(signer=signer)
    bad = verifier.verify(payload={'kind': 'rotate', 'target': 'wrong'}, envelope=envelope)
    assert bad.valid is False


def test_security_governance_secret_quarantine_and_recovery(tmp_path: Path) -> None:
    approvals = SignedOperatorApprovalStore(str(tmp_path / 'approvals.sqlite3'), 'secret')
    approvals.grant(
        approval_id='a1',
        operation_kind='key_rotate',
        actor='tester',
        payload={'ticket': 'SEC-2'},
    )
    incidents = SQLiteSecurityIncidentRegistry(str(tmp_path / 'incidents.sqlite3'))
    quarantine = SQLiteSecurityQuarantineRegistry(str(tmp_path / 'quarantine.sqlite3'))
    recovery = SecurityIncidentRecoveryOrchestrator(
        incident_registry=incidents,
        quarantine_registry=quarantine,
        audit_chain=SQLiteSecurityAuditChain(str(tmp_path / 'audit_chain.sqlite3')),
        drill_history=SQLiteSecurityIncidentDrillHistory(str(tmp_path / 'drills.sqlite3')),
    )
    orchestrator = SecurityGovernanceOrchestrator(
        approval_gate=SecurityApprovalGate(),
        approval_store=approvals,
        incident_registry=incidents,
        revocation_store=SQLiteTokenRevocationStore(str(tmp_path / 'revoked.sqlite3')),
        quarantine_registry=quarantine,
        audit_chain=SQLiteSecurityAuditChain(str(tmp_path / 'audit_chain.sqlite3')),
        workflow_store=SQLiteSecurityOperatorWorkflowStore(str(tmp_path / 'workflow.sqlite3')),
        recovery_orchestrator=recovery,
    )

    quarantine_report = orchestrator.quarantine_compromised_secret(
        secret_id='tenant:a:connector:crm:credential:token',
        actor='tester',
        reason='suspected leak',
    )
    assert quarantine_report.success is True
    assert quarantine.is_quarantined(entity_kind='secret', entity_id='tenant:a:connector:crm:credential:token') is True

    incident_id = quarantine_report.details['incident_id']
    recovery_report = orchestrator.recover_quarantined_entity(
        incident_id=incident_id,
        entity_kind='secret',
        entity_id='tenant:a:connector:crm:credential:token',
        actor='tester',
        resolution_payload={'resolution': 'rotated upstream'},
    )
    assert recovery_report.success is True
    assert quarantine.is_quarantined(entity_kind='secret', entity_id='tenant:a:connector:crm:credential:token') is False
