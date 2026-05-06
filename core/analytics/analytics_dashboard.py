from __future__ import annotations

import time
from dataclasses import dataclass

from core.contracts.analytics_dashboard import AnalyticsDashboard, DashboardSectionState


def _section_score_from_state(state: str) -> float:
    if state == 'healthy':
        return 1.0
    if state == 'warning':
        return 0.6
    if state == 'critical':
        return 0.2
    return 0.0


@dataclass(frozen=True)
class AnalyticsDashboardService:
    def build_dashboard(self, *, tenant_id: str, window_days: int, business_scorecard) -> AnalyticsDashboard:
        business_state = str(business_scorecard.diagnosis.overall_state)
        business_score = float(getattr(business_scorecard.diagnosis, 'score', _section_score_from_state(business_state)))
        sections = {
            'business': DashboardSectionState(
                section_id='business',
                state=business_state,
                score=business_score,
                payload={
                    'revenue_total': business_scorecard.revenue.revenue_total,
                    'retention_ratio': business_scorecard.retention.retention_ratio,
                    'execution_ratio': business_scorecard.decisions.execution_ratio,
                    'blocked_ratio': business_scorecard.decisions.blocked_ratio,
                    'latency_p95_ms': business_scorecard.latency.p95_ms,
                },
            )
        }
        overall_state = business_state
        overall_score = round(sum(s.score for s in sections.values()) / max(len(sections), 1), 4)
        highlights = tuple(f'business:{h}' for h in business_scorecard.diagnosis.highlights)
        risks = tuple(f'business:{r}' for r in business_scorecard.diagnosis.reasons if r != 'no_major_issues_detected')
        return AnalyticsDashboard(
            tenant_id=str(tenant_id),
            window_days=int(window_days),
            overall_state=overall_state,
            overall_score=overall_score,
            sections=sections,
            highlights=highlights,
            risks=risks,
            generated_at_ms=int(time.time() * 1000),
        )
