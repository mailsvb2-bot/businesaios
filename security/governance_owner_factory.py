from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from security.approval_replay_guard import SQLiteApprovalReplayGuard
from security.security_approval_gate import SecurityApprovalGate
from security.signed_operator_approval import SignedOperatorApprovalStore
from security.security_incident_registry import SQLiteSecurityIncidentRegistry
from security.token_revocation_store import SQLiteTokenRevocationStore
from security.security_quarantine_registry import SQLiteSecurityQuarantineRegistry
from security.security_audit_chain import SQLiteSecurityAuditChain
from security.security_operator_workflow_store import SQLiteSecurityOperatorWorkflowStore
from security.security_incident_drill_history import SQLiteSecurityIncidentDrillHistory
from security.security_incident_recovery_orchestrator import SecurityIncidentRecoveryOrchestrator
from security.security_governance_orchestrator import SecurityGovernanceOrchestrator
from security.audit_redaction_policy import AuditRedactionPolicy
from security.external_audit_export_signer import ExternalAuditExportSigner
from security.audit_export_verifier import AuditExportVerifier
from security.security_audit_export_service import SecurityAuditExportService
from security.security_drill_executor import SecurityDrillExecutor
from security.kms_provider_registry import KMSProviderRegistry
from security.kms_provider_inmemory import InMemoryKMSProvider
from security.kms_provider_sqlite import SQLiteKMSProvider


CANON_SECURITY_GOVERNANCE_OWNER_FACTORY = True


@dataclass(frozen=True)
class SecurityGovernanceInfrastructureOwner:
    governance: SecurityGovernanceOrchestrator
    recovery: SecurityIncidentRecoveryOrchestrator
    export_service: SecurityAuditExportService
    replay_guard: SQLiteApprovalReplayGuard
    drill_executor: SecurityDrillExecutor
    kms_registry: KMSProviderRegistry


def build_security_governance_infrastructure(*, base_dir: str | Path, shared_secret: str) -> SecurityGovernanceInfrastructureOwner:
    root = Path(base_dir)
    root.mkdir(parents=True, exist_ok=True)

    approvals = SignedOperatorApprovalStore(str(root / 'signed_operator_approvals.sqlite3'), shared_secret)
    incidents = SQLiteSecurityIncidentRegistry(str(root / 'security_incidents.sqlite3'))
    revoked = SQLiteTokenRevocationStore(str(root / 'security_revoked_tokens.sqlite3'))
    quarantine = SQLiteSecurityQuarantineRegistry(str(root / 'security_quarantine.sqlite3'))
    audit_chain = SQLiteSecurityAuditChain(str(root / 'security_audit_chain.sqlite3'))
    workflow = SQLiteSecurityOperatorWorkflowStore(str(root / 'security_operator_workflow.sqlite3'))
    drill_history = SQLiteSecurityIncidentDrillHistory(str(root / 'security_incident_drills.sqlite3'))
    replay_guard = SQLiteApprovalReplayGuard(str(root / 'security_consumed_approvals.sqlite3'))

    recovery = SecurityIncidentRecoveryOrchestrator(
        incident_registry=incidents,
        quarantine_registry=quarantine,
        audit_chain=audit_chain,
        drill_history=drill_history,
    )
    governance = SecurityGovernanceOrchestrator(
        approval_gate=SecurityApprovalGate(),
        approval_store=approvals,
        incident_registry=incidents,
        revocation_store=revoked,
        quarantine_registry=quarantine,
        audit_chain=audit_chain,
        workflow_store=workflow,
        recovery_orchestrator=recovery,
        approval_replay_guard=replay_guard,
    )
    export_service = SecurityAuditExportService(
        redaction_policy=AuditRedactionPolicy(),
        signer=ExternalAuditExportSigner(shared_secret),
        verifier=AuditExportVerifier(shared_secret),
    )
    drill_executor = SecurityDrillExecutor(governance=governance)
    kms_registry = KMSProviderRegistry()
    kms_registry.register(InMemoryKMSProvider())
    kms_registry.register(SQLiteKMSProvider(str(root / 'sqlite_kms.sqlite3')))
    return SecurityGovernanceInfrastructureOwner(
        governance=governance,
        recovery=recovery,
        export_service=export_service,
        replay_guard=replay_guard,
        drill_executor=drill_executor,
        kms_registry=kms_registry,
    )


__all__ = [
    'CANON_SECURITY_GOVERNANCE_OWNER_FACTORY',
    'SecurityGovernanceInfrastructureOwner',
    'build_security_governance_infrastructure',
]
