from __future__ import annotations

"""Canonical security primitives namespace.

This namespace owns cross-cutting security contracts, secret access,
redaction, signing helpers, and execution guard policies.
It must not contain business decision logic and must never become a second brain.
"""

from security.audit_redaction_policy import AuditRedactionPolicy
from security.access_policy import AccessPolicyVerdict, DataAccessPolicy, SecurityAction, SecurityResource
from security.anomaly_detector import AnomalyDetector, AnomalyVerdict
from security.behavioral_baseline import BaselineSample, BehavioralBaseline
from security.compliance_engine import ComplianceEngine, ComplianceVerdict
from security.compliance_reporter import ComplianceReporter
from security.fraud_detection_engine import FraudDetectionEngine, FraudVerdict
from security.security_integration_adapter import SecurityIntegrationAdapter
from security.security_policy_engine import SecurityEvaluationResult, SecurityPolicyEngine
from security.connector_secret_scope import ConnectorSecretScope, SecretAccessOperation, SecretScopeBinding
from security.credential_manager import CredentialHandle, CredentialManager
from security.credential_rotation_policy import CredentialRotationPolicy, RotationDecision
from security.encryption_policy import EncryptionAlgorithm, EncryptionPolicy
from security.key_management_contract import KeyMaterialRecord, KeyPurpose, KeyStatus
from security.key_provider import FileKeyProvider, InMemoryKeyProvider, KeyProvider, build_default_key_provider
from security.key_provider_sqlite import SqliteKeyProvider, SqliteKeyProviderBackend
from security.payload_redaction import PayloadRedactor
from security.pii_redaction_policy import PIIRedactionPolicy
from security.request_signing import RequestSigner, SignedRequestEnvelope
from security.sandbox_execution_policy import SandboxExecutionPolicy, SandboxExecutionVerdict
from security.secret_contract import SecretRecord, SecretRef, SecretSource, SecretState
from security.secret_vault import FileSecretVault, InMemorySecretVault, SecretVault, SqliteSecretVault, build_default_secret_vault
from security.secret_vault_sqlite import SqliteSecretVaultBackend
from security.session_policy import SessionPolicy, SessionVerdict
from security.token_policy import TokenPolicy, TokenVerdict
from security.webhook_signature_verifier import WebhookSignatureVerifier, WebhookVerificationResult

from security.owner_factory import (
    CANON_SECURITY_OWNER_FACTORY,
    SecurityInfrastructureOwner,
    build_default_security_adapter,
    build_security_infrastructure,
)
from security.request_signature_verifier import RequestSignatureVerifier, RequestVerificationResult
from security.security_audit_event_store import SQLiteSecurityAuditEventStore
from security.security_audit_chain import SQLiteSecurityAuditChain
from security.tenant_secret_scope import TenantSecretScope
from security.tenant_secret_access_policy import TenantSecretAccessPolicy, TenantSecretAccessVerdict
from security.key_rotation_policy import KeyRotationPolicy, KeyRotationVerdict
from security.key_rotation_journal import SQLiteKeyRotationJournal
from security.security_approval_gate import SecurityApprovalGate, SecurityApprovalVerdict
from security.reencryption_orchestrator import ReencryptionOrchestrator, ReencryptionReport
from security.signed_operator_approval import SignedOperatorApprovalStore

CANON_SECURITY_PUBLIC_API = True

__all__ = [
    'AccessPolicyVerdict',
    'AnomalyDetector',
    'AnomalyVerdict',
    'AuditRedactionPolicy',
    'BaselineSample',
    'BehavioralBaseline',
    'ComplianceEngine',
    'ComplianceReporter',
    'ComplianceVerdict',
    'DataAccessPolicy',
    'build_default_secret_vault',
    'CANON_SECURITY_PUBLIC_API',
    'ConnectorSecretScope',
    'SecretAccessOperation',
    'CredentialHandle',
    'CredentialManager',
    'CredentialRotationPolicy',
    'build_default_key_provider',
    'EncryptionAlgorithm',
    'EncryptionPolicy',
    'FileKeyProvider',
    'FileSecretVault',
    'InMemoryKeyProvider',
    'InMemorySecretVault',
    'KeyMaterialRecord',
    'KeyProvider',
    'KeyPurpose',
    'KeyStatus',
    'SqliteKeyProvider',
    'SqliteKeyProviderBackend',
    'PIIRedactionPolicy',
    'PayloadRedactor',
    'RequestSigner',
    'RotationDecision',
    'SandboxExecutionPolicy',
    'SandboxExecutionVerdict',
    'FraudDetectionEngine',
    'CANON_SECURITY_OWNER_FACTORY',
    'FraudVerdict',
    'SecurityAction',
    'SecurityEvaluationResult',
    'SecurityInfrastructureOwner',
    'SecurityIntegrationAdapter',
    'SecurityPolicyEngine',
    'build_default_security_adapter',
    'build_security_infrastructure',
    'SecurityResource',
    'SecretRecord',
    'SecretRef',
    'SecretScopeBinding',
    'SecretSource',
    'SecretState',
    'SecretVault',
    'SqliteSecretVault',
    'SqliteSecretVaultBackend',
    'SessionPolicy',
    'SessionVerdict',
    'SignedRequestEnvelope',
    'TokenPolicy',
    'TokenVerdict',
    'WebhookSignatureVerifier',
    'WebhookVerificationResult',
    'KMSKeyHandle',
    'KMSProvider',
    'KMSProviderCapability',
    'KMSProviderRegistry',
    'KMSRegistryEntry',
    'SQLiteSecurityIncidentRegistry',
    'SQLiteTokenRevocationStore',
    'EmergencyRevokeReport',
    'EmergencySecurityRevoke',
    'AuditExportVerifier',
    'ExternalAuditExportSigner',
    'MassReencryptionExecutor',
    'MassReencryptionReport',
    'RequestSignatureVerifier',
    'InMemoryKMSProvider',
    'SQLiteSecurityQuarantineRegistry',
    'SecurityGovernanceOrchestrator',
    'SecurityGovernanceReport',
    'SQLiteSecurityOperatorWorkflowStore',
    'SQLiteSecurityIncidentDrillHistory',
    'SecurityAuditExportService',
    'SecurityIncidentRecoveryOrchestrator',
    'SecurityIncidentRecoveryReport',
    'SQLiteApprovalReplayGuard',
    'CANON_SECURITY_GOVERNANCE_OWNER_FACTORY',
    'SecurityGovernanceInfrastructureOwner',
    'build_security_governance_infrastructure',
    'SQLiteKMSProvider',
]


from security.kms_provider_contract import KMSKeyHandle, KMSProvider, KMSProviderCapability
from security.kms_provider_registry import KMSProviderRegistry, KMSRegistryEntry
from security.security_incident_registry import SQLiteSecurityIncidentRegistry
from security.token_revocation_store import SQLiteTokenRevocationStore
from security.emergency_security_revoke import EmergencyRevokeReport, EmergencySecurityRevoke
from security.audit_export_verifier import AuditExportVerifier
from security.external_audit_export_signer import ExternalAuditExportSigner
from security.mass_reencryption_executor import MassReencryptionExecutor, MassReencryptionReport
from security.kms_provider_inmemory import InMemoryKMSProvider
from security.security_quarantine_registry import SQLiteSecurityQuarantineRegistry
from security.security_governance_orchestrator import SecurityGovernanceOrchestrator, SecurityGovernanceReport

from security.security_operator_workflow_store import SQLiteSecurityOperatorWorkflowStore
from security.security_incident_drill_history import SQLiteSecurityIncidentDrillHistory
from security.security_audit_export_service import SecurityAuditExportService
from security.security_incident_recovery_orchestrator import SecurityIncidentRecoveryOrchestrator, SecurityIncidentRecoveryReport

from security.approval_replay_guard import SQLiteApprovalReplayGuard
from security.governance_owner_factory import (
    CANON_SECURITY_GOVERNANCE_OWNER_FACTORY,
    SecurityGovernanceInfrastructureOwner,
    build_security_governance_infrastructure,
)

from security.kms_provider_sqlite import SQLiteKMSProvider
from security.security_drill_executor import SecurityDrillExecutor, SecurityDrillReport
