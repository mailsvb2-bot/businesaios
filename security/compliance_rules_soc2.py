from __future__ import annotations

"""Deterministic compliance rules for security posture evaluation."""

from dataclasses import dataclass, field
from typing import Mapping


CANON_SECURITY_COMPLIANCE_RULES_SOC2 = True


@dataclass(frozen=True)
class ComplianceRuleResult:
    control_id: str
    severity: str
    passed: bool
    reason: str
    evidence: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ComplianceRule:
    control_id: str
    severity: str
    description: str

    def evaluate(self, evidence: Mapping[str, object]) -> ComplianceRuleResult:
        passed = bool(evidence.get(self.control_id))
        return ComplianceRuleResult(
            control_id=self.control_id,
            severity=self.severity,
            passed=passed,
            reason='control_satisfied' if passed else 'control_missing',
            evidence={self.control_id: evidence.get(self.control_id)},
        )


SOC2_BASELINE_RULES: tuple[ComplianceRule, ...] = (
    ComplianceRule(control_id='encryption_at_rest', severity='critical', description='Sensitive data is encrypted at rest.'),
    ComplianceRule(control_id='encryption_in_transit', severity='critical', description='Sensitive data is encrypted in transit.'),
    ComplianceRule(control_id='immutable_audit_log', severity='critical', description='Audit trail is append-only and tamper-evident.'),
    ComplianceRule(control_id='rbac_enforced', severity='high', description='Role-based access control is enforced.'),
    ComplianceRule(control_id='session_policy_enforced', severity='high', description='Bounded session policy is enforced.'),
    ComplianceRule(control_id='token_policy_enforced', severity='high', description='Bounded token policy is enforced.'),
    ComplianceRule(control_id='secret_rotation', severity='medium', description='Secrets are rotated on policy.'),
    ComplianceRule(control_id='fraud_monitoring', severity='medium', description='Fraud and anomaly monitoring is active.'),
)


__all__ = [
    'CANON_SECURITY_COMPLIANCE_RULES_SOC2',
    'ComplianceRule',
    'ComplianceRuleResult',
    'SOC2_BASELINE_RULES',
]
