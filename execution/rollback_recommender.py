from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CANON_MEMORY_AWARE_ROLLBACK_RECOMMENDER = True

@dataclass(frozen=True)
class RollbackRecommendation:
    should_rollback: bool
    confidence: float
    reason: str
    recommended_run_id: str | None = None

@dataclass(frozen=True)
class MemoryAwareRollbackRecommender:
    high_severity_threshold: float = 0.70

    def recommend(self, *, candidate_record: dict[str, Any], baseline_record: dict[str, Any], drift_payload: dict[str, Any], business_memory_summary: dict[str, Any], fallback_candidates: list[dict[str, Any]]) -> RollbackRecommendation:
        severity = str(drift_payload.get('severity') or 'none')
        recurring_failures = list(business_memory_summary.get('recurring_failures') or [])
        candidate_feedback = dict(candidate_record.get('final_feedback') or {})
        candidate_error = str(candidate_feedback.get('error') or '')
        baseline_run_id = str(baseline_record.get('source_run_id') or baseline_record.get('run_id') or '')
        confidence = 0.0
        reasons: list[str] = []
        if severity == 'high':
            confidence += 0.55
            reasons.append('high_drift')
        elif severity == 'medium':
            confidence += 0.30
            reasons.append('medium_drift')
        if candidate_error and candidate_error in recurring_failures:
            confidence += 0.20
            reasons.append('repeated_known_failure')
        if str(candidate_record.get('stop_reason') or '') != 'goal_reached':
            confidence += 0.10
            reasons.append('candidate_not_goal_reached')
        recommended_run_id: str | None = None
        if fallback_candidates:
            best = sorted(fallback_candidates, key=lambda row: (1 if bool(row.get('completed')) else 0, float(dict(row.get('final_feedback') or {}).get('goal_score') or 0.0)), reverse=True)[0]
            recommended_run_id = str(best.get('run_id') or '')
            if recommended_run_id and recommended_run_id != baseline_run_id:
                reasons.append('better_fallback_candidate_found')
            elif baseline_run_id:
                recommended_run_id = baseline_run_id
                reasons.append('fallback_to_current_baseline')
        bounded = max(0.0, min(1.0, float(confidence)))
        return RollbackRecommendation(should_rollback=bounded >= float(self.high_severity_threshold), confidence=bounded, reason=','.join(reasons) if reasons else 'no_rollback_signal', recommended_run_id=recommended_run_id)

__all__ = ['CANON_MEMORY_AWARE_ROLLBACK_RECOMMENDER', 'MemoryAwareRollbackRecommender', 'RollbackRecommendation']
