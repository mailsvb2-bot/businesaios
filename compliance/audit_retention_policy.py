from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional

from compliance.base import PolicyMetadata
from compliance.data_retention_policy import DataRetentionPolicy, RetentionDecision


class AuditRecordType(str, Enum):
    DECISION_TRACE = 'decision_trace'
    ACTION_AUDIT = 'action_audit'
    SECURITY_AUDIT = 'security_audit'
    ACCESS_AUDIT = 'access_audit'
    EVIDENCE_LOG = 'evidence_log'
    EXPORT_AUDIT = 'export_audit'


@dataclass(frozen=True)
class AuditRetentionRule:
    record_type: AuditRecordType
    profile: str
    immutable: bool = True
    notes: tuple[str, ...] = ()


class AuditRetentionPolicy:
    def __init__(
        self,
        data_retention_policy: Optional[DataRetentionPolicy] = None,
        rules: Optional[Mapping[AuditRecordType, AuditRetentionRule]] = None,
        *,
        policy_version: str = '2.0',
    ) -> None:
        self._policy = PolicyMetadata(
            policy_name='audit_retention_policy',
            policy_version=policy_version,
            tags=('audit', 'retention'),
        )
        self._retention = data_retention_policy or DataRetentionPolicy(policy_version=policy_version)
        self._rules = dict(
            rules
            or {
                AuditRecordType.DECISION_TRACE: AuditRetentionRule(AuditRecordType.DECISION_TRACE, 'audit_immutable'),
                AuditRecordType.ACTION_AUDIT: AuditRetentionRule(AuditRecordType.ACTION_AUDIT, 'audit_immutable'),
                AuditRecordType.SECURITY_AUDIT: AuditRetentionRule(AuditRecordType.SECURITY_AUDIT, 'audit_immutable'),
                AuditRecordType.ACCESS_AUDIT: AuditRetentionRule(AuditRecordType.ACCESS_AUDIT, 'audit_immutable'),
                AuditRecordType.EVIDENCE_LOG: AuditRetentionRule(AuditRecordType.EVIDENCE_LOG, 'regulated'),
                AuditRecordType.EXPORT_AUDIT: AuditRetentionRule(AuditRecordType.EXPORT_AUDIT, 'audit_immutable'),
            }
        )

    def evaluate(self, record_type: AuditRecordType, *, legal_hold: bool = False) -> RetentionDecision:
        return self._retention.evaluate(profile=self._rules[record_type].profile, legal_hold=legal_hold)
    decide = evaluate
