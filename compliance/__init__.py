from __future__ import annotations

"""Canonical compliance primitives namespace.

This namespace is a policy/guard layer only.
It must never become a planner, strategy engine, or alternative DecisionCore.
"""

from compliance.action_compliance_policy import ActionComplianceInput, ActionCompliancePolicy, ActionComplianceVerdict
from compliance.approval_compliance_policy import (
    ApprovalComplianceInput,
    ApprovalCompliancePolicy,
    ApprovalComplianceVerdict,
    ApprovalRequirement,
)
from compliance.audit_retention_policy import AuditRecordType, AuditRetentionPolicy, AuditRetentionRule
from compliance.base import (
    ComplianceControl,
    ComplianceDeniedError,
    ComplianceError,
    CompliancePolicyError,
    ComplianceValidationError,
    ComplianceVerdictStatus,
    PolicyMetadata,
)
from compliance.compliance_bundle import ComplianceBundle, ComplianceBundleInput, ComplianceBundleVerdict
from compliance.connector_compliance_matrix import (
    ConnectorComplianceDecision,
    ConnectorComplianceMatrix,
    ConnectorComplianceRecord,
    ConnectorRiskTier,
)
from compliance.data_classification import (
    DataAsset,
    DataCategory,
    DataClassificationResult,
    DataClassifier,
    DataSensitivity,
    KeywordDataClassifier,
)
from compliance.data_retention_policy import DataRetentionPolicy, DataRetentionRule, RetentionDecision, RetentionPolicyLevel
from compliance.evidence_export_contract import (
    EvidenceExportFormat,
    EvidenceExportManifest,
    EvidenceExportRequest,
    EvidenceExportResult,
    EvidenceExporter,
    EvidenceRecord,
)
from compliance.evidence_export_service import EvidenceExportService, InMemoryEvidenceExporter
from compliance.evidence_export_store import EvidenceExportStore, JsonlEvidenceExportStore, StoredEvidenceExportRecord
from compliance.pii_guard import PIIGuard, PiiFinding, PiiGuardResult, PiiType
from compliance.policy_registry import PolicyRegistry, PolicySnapshot
from compliance.regional_data_policy import DataRegion, RegionalDataPolicy, RegionalPolicyDecision

CANON_COMPLIANCE_PUBLIC_API = True

__all__ = [
    'ActionComplianceInput',
    'ActionCompliancePolicy',
    'ActionComplianceVerdict',
    'ApprovalComplianceInput',
    'ApprovalCompliancePolicy',
    'ApprovalComplianceVerdict',
    'ApprovalRequirement',
    'AuditRecordType',
    'AuditRetentionPolicy',
    'AuditRetentionRule',
    'CANON_COMPLIANCE_PUBLIC_API',
    'ComplianceBundle',
    'ComplianceBundleInput',
    'ComplianceBundleVerdict',
    'ComplianceControl',
    'ComplianceDeniedError',
    'ComplianceError',
    'CompliancePolicyError',
    'ComplianceValidationError',
    'ComplianceVerdictStatus',
    'ConnectorComplianceDecision',
    'ConnectorComplianceMatrix',
    'ConnectorComplianceRecord',
    'ConnectorRiskTier',
    'DataAsset',
    'DataCategory',
    'DataClassificationResult',
    'DataClassifier',
    'DataRegion',
    'DataRetentionPolicy',
    'DataRetentionRule',
    'DataSensitivity',
    'EvidenceExportFormat',
    'EvidenceExporter',
    'EvidenceExportManifest',
    'EvidenceExportRequest',
    'EvidenceExportResult',
    'EvidenceExportService',
    'EvidenceExportStore',
    'EvidenceRecord',
    'InMemoryEvidenceExporter',
    'JsonlEvidenceExportStore',
    'KeywordDataClassifier',
    'PIIGuard',
    'PolicyMetadata',
    'PolicyRegistry',
    'PolicySnapshot',
    'PiiFinding',
    'PiiGuardResult',
    'PiiType',
    'RegionalDataPolicy',
    'RegionalPolicyDecision',
    'RetentionDecision',
    'RetentionPolicyLevel',
    'StoredEvidenceExportRecord',
]
