from __future__ import annotations

import time
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
from security.governance_journal import SQLiteGovernanceJournal
from security.reencryption_job_store import SQLiteReencryptionJobStore
from security.security_drill_schedule_store import SecurityDrillSchedule, SQLiteSecurityDrillScheduleStore
from security.security_runtime_summary import SecurityRuntimeSummaryService
from security.tenant_security_isolation import TenantScopedSecurityIsolation
from security.security_pressure_monitor import SecurityPressureMonitor


CANON_SECURITY_GOVERNANCE_OWNER_FACTORY = True


@dataclass(frozen=True)
class CryptoAgilityProfile:
    profile_name: str
    signing_algorithm: str
    encryption_algorithm: str
    status: str = 'active'


class SecurityCryptoAgilityService:
    def list_profiles(self) -> tuple[CryptoAgilityProfile, ...]:
        return (
            CryptoAgilityProfile(profile_name='baseline-v1', signing_algorithm='hmac-sha256', encryption_algorithm='aes256_gcm'),
            CryptoAgilityProfile(profile_name='post-quantum-ready', signing_algorithm='hybrid-ed25519-dilithium', encryption_algorithm='aes256_gcm+kyber'),
        )


class SecurityDrillRuntime:
    def __init__(self, *, schedule_store: SQLiteSecurityDrillScheduleStore, drill_executor: SecurityDrillExecutor) -> None:
        self._schedule_store = schedule_store
        self._drill_executor = drill_executor

    def schedule(self, schedule: SecurityDrillSchedule) -> None:
        self._schedule_store.put(schedule)

    def run_due(self, *, now_epoch_s: int | None = None, limit: int = 50) -> tuple[object, ...]:
        resolved_now = int(time.time()) if now_epoch_s is None else int(now_epoch_s)
        results: list[object] = []
        for item in self._schedule_store.due(now_epoch_s=resolved_now, limit=limit):
            if item.drill_kind == 'token_quarantine_recovery':
                result = self._drill_executor.run_token_quarantine_recovery_drill(
                    actor=item.actor,
                    token_fingerprint=item.target_entity_id,
                )
            else:
                result = self._drill_executor.run_secret_quarantine_recovery_drill(
                    actor=item.actor,
                    secret_id=item.target_entity_id,
                )
            results.append(result)
            self._schedule_store.mark_run(
                drill_id=item.drill_id,
                next_run_epoch_s=resolved_now + max(int(item.interval_seconds), 1),
            )
        return tuple(results)


@dataclass(frozen=True)
class SecurityGovernanceInfrastructureOwner:
    governance: SecurityGovernanceOrchestrator
    recovery: SecurityIncidentRecoveryOrchestrator
    export_service: SecurityAuditExportService
    replay_guard: SQLiteApprovalReplayGuard
    drill_executor: SecurityDrillExecutor
    kms_registry: KMSProviderRegistry
    governance_journal: SQLiteGovernanceJournal
    reencryption_jobs: SQLiteReencryptionJobStore
    drill_schedule_store: SQLiteSecurityDrillScheduleStore
    runtime_summary: SecurityRuntimeSummaryService
    tenant_isolation: TenantScopedSecurityIsolation
    crypto_agility: SecurityCryptoAgilityService
    drill_runtime: SecurityDrillRuntime
    pressure_monitor: SecurityPressureMonitor


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
    governance_journal = SQLiteGovernanceJournal(str(root / 'security_governance_journal.sqlite3'))
    reencryption_jobs = SQLiteReencryptionJobStore(str(root / 'security_reencryption_jobs.sqlite3'))
    drill_schedule_store = SQLiteSecurityDrillScheduleStore(str(root / 'security_drill_schedule.sqlite3'))

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
        governance_journal=governance_journal,
    )
    export_service = SecurityAuditExportService(
        redaction_policy=AuditRedactionPolicy(),
        signer=ExternalAuditExportSigner(shared_secret),
        verifier=AuditExportVerifier(shared_secret),
    )
    drill_executor = SecurityDrillExecutor(governance=governance)
    kms_registry = KMSProviderRegistry()
    kms_registry.register(InMemoryKMSProvider())
    kms_registry.register(InMemoryKMSProvider(provider_name='hardware-hsm', hsm_backed=True))
    kms_registry.register(InMemoryKMSProvider(provider_name='aws-kms', hsm_backed=True))
    kms_registry.register(InMemoryKMSProvider(provider_name='gcp-kms', hsm_backed=True))
    kms_registry.register(InMemoryKMSProvider(provider_name='vault-transit', hsm_backed=True))
    kms_registry.register(SQLiteKMSProvider(str(root / 'sqlite_kms.sqlite3')))
    runtime_summary = SecurityRuntimeSummaryService(
        incident_registry=incidents,
        quarantine_registry=quarantine,
        reencryption_job_store=reencryption_jobs,
        drill_history=drill_history,
        governance_journal=governance_journal,
    )
    tenant_isolation = TenantScopedSecurityIsolation(
        governance_journal=governance_journal,
        reencryption_jobs=reencryption_jobs,
        drill_schedule_store=drill_schedule_store,
        kms_registry=kms_registry,
        audit_export_service=export_service,
    )
    pressure_monitor = SecurityPressureMonitor(
        incident_registry=incidents,
        quarantine_registry=quarantine,
        reencryption_job_store=reencryption_jobs,
    )
    drill_runtime = SecurityDrillRuntime(schedule_store=drill_schedule_store, drill_executor=drill_executor)
    crypto_agility = SecurityCryptoAgilityService()
    return SecurityGovernanceInfrastructureOwner(
        governance=governance,
        recovery=recovery,
        export_service=export_service,
        replay_guard=replay_guard,
        drill_executor=drill_executor,
        kms_registry=kms_registry,
        governance_journal=governance_journal,
        reencryption_jobs=reencryption_jobs,
        drill_schedule_store=drill_schedule_store,
        runtime_summary=runtime_summary,
        tenant_isolation=tenant_isolation,
        crypto_agility=crypto_agility,
        drill_runtime=drill_runtime,
        pressure_monitor=pressure_monitor,
    )


__all__ = [
    'CANON_SECURITY_GOVERNANCE_OWNER_FACTORY',
    'CryptoAgilityProfile',
    'SecurityCryptoAgilityService',
    'SecurityDrillRuntime',
    'SecurityGovernanceInfrastructureOwner',
    'build_security_governance_infrastructure',
]
