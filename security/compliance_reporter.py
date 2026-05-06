from __future__ import annotations

"""Presentation-only compliance reporter."""

from dataclasses import dataclass
from typing import Any

from security.compliance_engine import ComplianceVerdict


CANON_SECURITY_COMPLIANCE_REPORTER = True


@dataclass(frozen=True)
class ComplianceReporter:
    def build_report(self, verdict: ComplianceVerdict) -> dict[str, Any]:
        return {
            'kind': 'security_compliance_report',
            'payload': {
                'compliant': verdict.compliant,
                'score': verdict.score,
                'passed_controls': list(verdict.passed_controls),
                'failed_controls': list(verdict.failed_controls),
                'critical_failure_ids': list(verdict.critical_failure_ids),
                'evidence_fingerprint': verdict.evidence_fingerprint,
                'results': [
                    {
                        'control_id': item.control_id,
                        'severity': item.severity,
                        'passed': item.passed,
                        'reason': item.reason,
                        'evidence': dict(item.evidence),
                    }
                    for item in verdict.results
                ],
            },
        }


__all__ = [
    'CANON_SECURITY_COMPLIANCE_REPORTER',
    'ComplianceReporter',
]
