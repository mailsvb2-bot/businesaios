from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class ComplianceError(Exception):
    """Base compliance error."""


class ComplianceValidationError(ComplianceError):
    """Raised when inputs are structurally invalid."""


class CompliancePolicyError(ComplianceError):
    """Raised when policy configuration is invalid."""


class ComplianceDeniedError(ComplianceError):
    """Raised for explicit fail-closed denial."""


class ComplianceControl(str, Enum):
    PII_REDACTION = 'pii_redaction'
    PAYLOAD_REDACTION = 'payload_redaction'
    SECRET_REDACTION = 'secret_redaction'
    EFFECT_AUDIT = 'effect_audit'
    EXPORT_AUDIT = 'export_audit'
    EVIDENCE_VERIFICATION = 'evidence_verification'
    APPROVAL = 'approval'
    RESTRICTED_SCOPE_GUARD = 'restricted_scope_guard'
    JURISDICTION_BASIS = 'jurisdiction_basis'
    TRANSFER_AUDIT = 'transfer_audit'
    PII_MINIMIZATION = 'pii_minimization'
    SECRET_SCOPE_ENFORCEMENT = 'secret_scope_enforcement'
    UPSTREAM_REDACTION_REQUIRED = 'upstream_redaction_required'
    RETENTION_EXCEPTION_REVIEW = 'retention_exception_review'
    ROLLBACK_OR_COMPENSATION = 'rollback_or_compensation'
    IDEMPOTENCY_KEY = 'idempotency_key'
    LEGAL_BASIS_REVIEW = 'legal_basis_review'
    CSV_FORMULA_HARDENING = 'csv_formula_hardening'


class ComplianceVerdictStatus(str, Enum):
    ALLOWED = 'allowed'
    OPERATOR_REQUIRED = 'operator_required'
    DENIED = 'denied'


@dataclass(frozen=True)
class PolicyMetadata:
    policy_name: str
    policy_version: str
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)
