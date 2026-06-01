from __future__ import annotations

import time
from dataclasses import dataclass

from core.contracts.analytics_explainability_trace import (
    AnalyticsExplainabilityTrace,
    ExplainabilityEvidence,
    ExplainabilityReason,
)


@dataclass(frozen=True)
class AnalyticsExplainabilityService:
    def build_from_business_scorecard(self, *, scorecard) -> AnalyticsExplainabilityTrace:
        evidence = {
            'retention.retention_ratio': ExplainabilityEvidence('retention.retention_ratio', 'retention', 'retention_ratio', scorecard.retention.retention_ratio),
            'decision.execution_ratio': ExplainabilityEvidence('decision.execution_ratio', 'execution', 'execution_ratio', scorecard.decisions.execution_ratio),
            'decision.blocked_ratio': ExplainabilityEvidence('decision.blocked_ratio', 'execution', 'blocked_ratio', scorecard.decisions.blocked_ratio),
            'latency.p95_ms': ExplainabilityEvidence('latency.p95_ms', 'latency', 'p95_ms', scorecard.latency.p95_ms),
            'revenue.total': ExplainabilityEvidence('revenue.total', 'revenue', 'revenue_total', scorecard.revenue.revenue_total),
        }
        reasons = []
        for reason in scorecard.diagnosis.reasons:
            linked = []
            if 'retention' in reason:
                linked.append('retention.retention_ratio')
            if 'blocked' in reason:
                linked.append('decision.blocked_ratio')
            if 'latency' in reason:
                linked.append('latency.p95_ms')
            if 'revenue' in reason:
                linked.append('revenue.total')
            if 'execution' in reason:
                linked.append('decision.execution_ratio')
            severity = 'critical' if scorecard.diagnosis.overall_state == 'critical' else 'warning' if scorecard.diagnosis.overall_state == 'warning' else 'info'
            reasons.append(ExplainabilityReason(reason_id=reason, severity=severity, summary=reason.replace('_', ' '), evidence_ids=linked))
        return AnalyticsExplainabilityTrace(
            tenant_id=str(scorecard.tenant_id),
            trace_kind='business_scorecard',
            reasons=reasons or [ExplainabilityReason(reason_id='no_major_issues_detected', severity='info', summary='no major issues detected', evidence_ids=list(evidence))],
            evidence=evidence,
            generated_at_ms=int(getattr(scorecard, 'generated_at_ms', int(time.time() * 1000))),
        )
