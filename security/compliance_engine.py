from __future__ import annotations

"""Security compliance evaluator.

Evaluates evidence against deterministic controls. No business decision logic.
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Mapping

from security.compliance_rules_soc2 import ComplianceRule, ComplianceRuleResult, SOC2_BASELINE_RULES


CANON_SECURITY_COMPLIANCE_ENGINE = True

_SEVERITY_WEIGHT = {
    'critical': 5,
    'high': 3,
    'medium': 2,
    'low': 1,
}


@dataclass(frozen=True)
class ComplianceVerdict:
    compliant: bool
    score: float
    passed_controls: tuple[str, ...]
    failed_controls: tuple[str, ...]
    critical_failure_ids: tuple[str, ...]
    evidence_fingerprint: str
    results: tuple[ComplianceRuleResult, ...]


@dataclass
class ComplianceEngine:
    rules: tuple[ComplianceRule, ...] = field(default_factory=lambda: SOC2_BASELINE_RULES)

    def evaluate(self, evidence: Mapping[str, object]) -> ComplianceVerdict:
        normalized_evidence = dict(evidence or {})
        results = tuple(rule.evaluate(normalized_evidence) for rule in self.rules)
        total_weight = sum(_SEVERITY_WEIGHT.get(result.severity, 1) for result in results)
        passed_weight = sum(_SEVERITY_WEIGHT.get(result.severity, 1) for result in results if result.passed)
        failed_controls = tuple(result.control_id for result in results if not result.passed)
        critical_failure_ids = tuple(result.control_id for result in results if (not result.passed and result.severity == 'critical'))
        score = 1.0 if total_weight <= 0 else max(0.0, min(1.0, passed_weight / total_weight))
        fingerprint = hashlib.sha256(json.dumps(normalized_evidence, ensure_ascii=False, sort_keys=True, default=str).encode('utf-8')).hexdigest()
        return ComplianceVerdict(
            compliant=not critical_failure_ids and not failed_controls,
            score=score,
            passed_controls=tuple(result.control_id for result in results if result.passed),
            failed_controls=failed_controls,
            critical_failure_ids=critical_failure_ids,
            evidence_fingerprint=fingerprint,
            results=results,
        )


__all__ = [
    'CANON_SECURITY_COMPLIANCE_ENGINE',
    'ComplianceEngine',
    'ComplianceVerdict',
]
