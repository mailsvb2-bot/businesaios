from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from security.approval_replay_guard import SQLiteApprovalReplayGuard
from security.audit_export_verifier import AuditExportVerifier
from security.audit_redaction_policy import AuditRedactionPolicy
from security.aws_kms_adapter import AWSKMSAdapter, AWSKMSConfig
from security.cryptographic_agility import CryptographicAgilityRegistry, CryptographicProfile
from security.external_audit_export_signer import ExternalAuditExportSigner
from security.external_audit_notarization import ExternalAuditNotarizationProvider
from security.external_timestamp_authority import ExternalTimestampAuthority
from security.gcp_kms_adapter import GCPKMSAdapter, GCPKMSConfig
from security.governance_journal import SQLiteGovernanceJournal
from security.hardware_hsm_client import HardwareHSMClient, HardwareHSMConfig
from security.kms_provider_inmemory import InMemoryKMSProvider
from security.kms_provider_registry import KMSProviderRegistry
from security.kms_provider_sqlite import SQLiteKMSProvider
from security.public_ledger_anchor import PublicLedgerAnchor
from security.reencryption_job_store import SQLiteReencryptionJobStore
from security.security_approval_gate import SecurityApprovalGate
from security.security_audit_chain import SQLiteSecurityAuditChain
from security.security_audit_export_service import SecurityAuditExportService
from security.security_chaos_mode import SecurityChaosMode
from security.security_drill_executor import SecurityDrillExecutor
from security.security_drill_runtime import SecurityDrillRuntime
from security.security_drill_schedule_store import SQLiteSecurityDrillScheduleStore
from security.security_governance_orchestrator import SecurityGovernanceOrchestrator
from security.security_incident_drill_history import SQLiteSecurityIncidentDrillHistory
from security.security_incident_recovery_orchestrator import SecurityIncidentRecoveryOrchestrator
from security.security_incident_registry import SQLiteSecurityIncidentRegistry
from security.security_operator_workflow_store import SQLiteSecurityOperatorWorkflowStore
from security.security_pressure_monitor import SecurityPressureMonitor
from security.security_quarantine_registry import SQLiteSecurityQuarantineRegistry
from security.security_runtime_summary import SecurityRuntimeSummaryService
from security.security_slo_model import SecuritySLOModel
from security.signed_operator_approval import SignedOperatorApprovalStore
from security.tenant_security_isolation import TenantScopedSecurityIsolation
from security.token_revocation_store import SQLiteTokenRevocationStore
from security.vault_transit_kms_adapter import VaultTransitConfig, VaultTransitKMSAdapter

CANON_SECURITY_GOVERNANCE_OWNER_FACTORY = True
CANON_EXTERNAL_ADAPTERS_LOCALLY_BACKED_BY_DEFAULT = True


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
    crypto_agility: CryptographicAgilityRegistry
    drill_runtime: SecurityDrillRuntime
    pressure_monitor: SecurityPressureMonitor
    chaos_mode: SecurityChaosMode
    slo_model: SecuritySLOModel


def _key_response(handle: Any) -> dict[str, object]:
    return {
        "key_id": handle.key_id,
        "key_version": handle.key_version,
        "algorithm": handle.algorithm,
        "exportable": handle.exportable,
    }


def _locally_backed_callbacks(
    *, provider_name: str, hsm_backed: bool
) -> tuple[Callable[..., dict[str, object]], Callable[..., dict[str, object]]]:
    """Build explicit local callbacks for an external adapter boundary.

    These callbacks make development/tests deterministic. They do not claim a live
    cloud/HSM connection; production may inject SDK-backed callables at composition.
    """

    backend = InMemoryKMSProvider(
        provider_name=provider_name,
        hsm_backed=hsm_backed,
    )

    def create_key_fn(**kwargs: Any) -> dict[str, object]:
        return _key_response(
            backend.create_key(
                key_id=str(kwargs["key_id"]),
                algorithm=str(kwargs["algorithm"]),
                exportable=bool(kwargs.get("exportable", False)),
                credential_ref=(
                    None
                    if kwargs.get("credential_ref") is None
                    else str(kwargs["credential_ref"])
                ),
            )
        )

    def get_active_key_fn(**kwargs: Any) -> dict[str, object]:
        return _key_response(
            backend.get_active_key(
                key_id=str(kwargs["key_id"]),
                credential_ref=(
                    None
                    if kwargs.get("credential_ref") is None
                    else str(kwargs["credential_ref"])
                ),
            )
        )

    return create_key_fn, get_active_key_fn


def _register_external_adapter_boundaries(provider_registry: KMSProviderRegistry) -> None:
    aws_create, aws_get = _locally_backed_callbacks(
        provider_name="aws-kms", hsm_backed=True
    )
    provider_registry.register(
        AWSKMSAdapter(
            AWSKMSConfig(region="local-development"),
            create_key_fn=aws_create,
            get_active_key_fn=aws_get,
        )
    )

    gcp_create, gcp_get = _locally_backed_callbacks(
        provider_name="gcp-kms", hsm_backed=True
    )
    provider_registry.register(
        GCPKMSAdapter(
            GCPKMSConfig(
                project_id="local-development",
                location="local",
                key_ring="businesaios",
            ),
            create_key_fn=gcp_create,
            get_active_key_fn=gcp_get,
        )
    )

    vault_create, vault_get = _locally_backed_callbacks(
        provider_name="vault-transit", hsm_backed=True
    )
    provider_registry.register(
        VaultTransitKMSAdapter(
            VaultTransitConfig(),
            create_key_fn=vault_create,
            get_active_key_fn=vault_get,
        )
    )

    hsm_create, hsm_get = _locally_backed_callbacks(
        provider_name="hardware-hsm", hsm_backed=True
    )
    provider_registry.register(
        HardwareHSMClient(
            HardwareHSMConfig(slot_id="local-development"),
            create_key_fn=hsm_create,
            get_active_key_fn=hsm_get,
        )
    )


def _build_local_notary() -> ExternalAuditNotarizationProvider:
    def stamp_fn(**kwargs: Any) -> dict[str, object]:
        now = int(time.time())
        digest = str(kwargs["payload_digest"])
        return {
            "timestamp_token": f"tsa::{now}::{digest[:16]}",
            "signed_at_epoch_s": now,
        }

    def verify_stamp_fn(**kwargs: Any) -> bool:
        digest = str(kwargs["payload_digest"])
        return str(kwargs["timestamp_token"]).endswith(digest[:16])

    def anchor_fn(**kwargs: Any) -> dict[str, object]:
        digest = str(kwargs["payload_digest"])
        return {
            "anchor_id": f"ledger::{digest}",
            "anchored_digest": digest,
        }

    def verify_anchor_fn(**kwargs: Any) -> bool:
        digest = str(kwargs["payload_digest"])
        return (
            str(kwargs["anchor_id"]) == f"ledger::{digest}"
            and str(kwargs["anchored_digest"]) == digest
        )

    return ExternalAuditNotarizationProvider(
        provider_name="local-notary",
        timestamp_authority=ExternalTimestampAuthority(
            authority_name="local-tsa",
            stamp_fn=stamp_fn,
            verify_fn=verify_stamp_fn,
        ),
        ledger_anchor=PublicLedgerAnchor(
            ledger_name="local-ledger",
            anchor_fn=anchor_fn,
            verify_fn=verify_anchor_fn,
        ),
    )


def _build_crypto_agility_registry() -> CryptographicAgilityRegistry:
    profile_registry = CryptographicAgilityRegistry()
    for profile in (
        CryptographicProfile(
            profile_name="default-sealed-box",
            encryption_algorithm="sealed-box-v1",
            signature_scheme="hmac-sha256",
            hash_algorithm="sha256",
            key_size_bits=256,
        ),
        CryptographicProfile(
            profile_name="regulated-aes-gcm",
            encryption_algorithm="aes256_gcm",
            signature_scheme="hmac-sha256",
            hash_algorithm="sha256",
            key_size_bits=256,
        ),
        CryptographicProfile(
            profile_name="post-quantum-ready",
            encryption_algorithm="aes256_gcm+kyber",
            signature_scheme="hybrid-ed25519-dilithium",
            hash_algorithm="sha512",
            key_size_bits=256,
        ),
    ):
        profile_registry.register(profile)
    return profile_registry


def build_security_governance_infrastructure(
    *, base_dir: str | Path, shared_secret: str
) -> SecurityGovernanceInfrastructureOwner:
    root = Path(base_dir)
    root.mkdir(parents=True, exist_ok=True)

    approvals = SignedOperatorApprovalStore(
        str(root / "signed_operator_approvals.sqlite3"), shared_secret
    )
    incidents = SQLiteSecurityIncidentRegistry(str(root / "security_incidents.sqlite3"))
    revoked = SQLiteTokenRevocationStore(str(root / "security_revoked_tokens.sqlite3"))
    quarantine = SQLiteSecurityQuarantineRegistry(
        str(root / "security_quarantine.sqlite3")
    )
    audit_chain = SQLiteSecurityAuditChain(str(root / "security_audit_chain.sqlite3"))
    workflow = SQLiteSecurityOperatorWorkflowStore(
        str(root / "security_operator_workflow.sqlite3")
    )
    drill_history = SQLiteSecurityIncidentDrillHistory(
        str(root / "security_incident_drills.sqlite3")
    )
    replay_guard = SQLiteApprovalReplayGuard(
        str(root / "security_consumed_approvals.sqlite3")
    )
    governance_journal = SQLiteGovernanceJournal(
        str(root / "security_governance_journal.sqlite3")
    )
    reencryption_jobs = SQLiteReencryptionJobStore(
        str(root / "security_reencryption_jobs.sqlite3")
    )
    drill_schedule_store = SQLiteSecurityDrillScheduleStore(
        str(root / "security_drill_schedule.sqlite3")
    )

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
        notarization_provider=_build_local_notary(),
    )
    drill_executor = SecurityDrillExecutor(governance=governance)

    kms_registry = KMSProviderRegistry()
    kms_registry.register(InMemoryKMSProvider())
    _register_external_adapter_boundaries(kms_registry)
    kms_registry.register(SQLiteKMSProvider(str(root / "sqlite_kms.sqlite3")))

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
        crypto_agility=_build_crypto_agility_registry(),
        drill_runtime=SecurityDrillRuntime(
            schedule_store=drill_schedule_store,
            drill_executor=drill_executor,
            incident_registry=incidents,
            governance_journal=governance_journal,
        ),
        pressure_monitor=pressure_monitor,
        chaos_mode=SecurityChaosMode(
            incident_registry=incidents,
            governance_journal=governance_journal,
        ),
        slo_model=SecuritySLOModel(),
    )


__all__ = [
    "CANON_EXTERNAL_ADAPTERS_LOCALLY_BACKED_BY_DEFAULT",
    "CANON_SECURITY_GOVERNANCE_OWNER_FACTORY",
    "SecurityGovernanceInfrastructureOwner",
    "build_security_governance_infrastructure",
]
