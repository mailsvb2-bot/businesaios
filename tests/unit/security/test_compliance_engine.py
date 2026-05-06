from __future__ import annotations

from security.compliance_engine import ComplianceEngine


def test_compliance_engine_reports_critical_failures() -> None:
    verdict = ComplianceEngine().evaluate(
        {
            'encryption_at_rest': True,
            'encryption_in_transit': False,
            'immutable_audit_log': True,
            'rbac_enforced': True,
            'session_policy_enforced': True,
            'token_policy_enforced': True,
            'secret_rotation': False,
            'fraud_monitoring': True,
        }
    )
    assert verdict.compliant is False
    assert 'encryption_in_transit' in verdict.critical_failure_ids
    assert verdict.score < 1.0
    assert len(verdict.evidence_fingerprint) == 64
