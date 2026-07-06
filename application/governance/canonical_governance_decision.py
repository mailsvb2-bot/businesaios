from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CANON_GOVERNANCE_DECISION_CONTRACT = True


def _text(value: Any) -> str:
    return str(value or '').strip()


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list | tuple) else []


def _safe_bool(value: Any) -> bool:
    return bool(value)


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _fit_report_payload(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        payload = dict(value)
        return {
            'approved': _safe_bool(payload.get('approved')),
            'score': _safe_float(payload.get('score')),
            'reasons': [str(x) for x in _safe_list(payload.get('reasons')) if str(x)],
            'summary': _text(payload.get('summary')),
        }
    return {
        'approved': _safe_bool(getattr(value, 'approved', False)),
        'score': _safe_float(getattr(value, 'score', 0.0)),
        'reasons': [str(x) for x in _safe_list(getattr(value, 'reasons', ())) if str(x)],
        'summary': _text(getattr(value, 'summary', '')),
    }


def _promotion_decision_payload(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        payload = dict(value)
        reasons = [str(x) for x in _safe_list(payload.get('reasons')) if str(x)]
        reason = _text(payload.get('reason'))
        if reason and reason not in reasons:
            reasons.append(reason)
        return {
            'approved': _safe_bool(payload.get('approved')),
            'reason': reason,
            'reasons': reasons,
        }
    reason = _text(getattr(value, 'reason', ''))
    reasons = [reason] if reason else []
    return {
        'approved': _safe_bool(getattr(value, 'approved', False)),
        'reason': reason,
        'reasons': reasons,
    }


def canonical_governance_decision(
    *,
    decision_type: str,
    baseline_name: str = '',
    candidate_run_id: str = '',
    selected_run_id: str = '',
    approved: bool = False,
    confidence: float = 0.0,
    reasons: list[str] | tuple[str, ...] | None = None,
    summary: str = '',
    metadata: Mapping[str, Any] | None = None,
    governance_evidence: Mapping[str, Any] | None = None,
    fit_report: Any = None,
    promotion_decision: Any = None,
    ranked_candidates: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    selected = _text(selected_run_id or candidate_run_id)
    fit_payload = _fit_report_payload(fit_report)
    promotion_payload = _promotion_decision_payload(promotion_decision)
    normalized_reasons = [str(x) for x in _safe_list(reasons) if str(x)]
    for source_reasons in (fit_payload.get('reasons') or [], promotion_payload.get('reasons') or []):
        for item in source_reasons:
            if item and item not in normalized_reasons:
                normalized_reasons.append(item)
    if promotion_payload.get('reason') and promotion_payload['reason'] not in normalized_reasons:
        normalized_reasons.append(promotion_payload['reason'])
    return {
        'governance_decision': {
            'decision_type': _text(decision_type),
            'baseline_name': _text(baseline_name),
            'candidate_run_id': _text(candidate_run_id),
            'selected_run_id': selected,
            'approved': _safe_bool(approved),
            'confidence': max(0.0, min(1.0, _safe_float(confidence))),
            'reasons': normalized_reasons,
            'summary': _text(summary),
            'fit_report': fit_payload,
            'promotion_gate': promotion_payload,
            'ranked_candidates': [dict(item) for item in (ranked_candidates or []) if isinstance(item, Mapping)],
            'governance_evidence': _safe_dict(governance_evidence),
            'metadata': _safe_dict(metadata),
        }
    }


def canonical_baseline_selection_decision(
    *,
    baseline_name: str = '',
    selected_record: Mapping[str, Any] | None,
    ranked_candidates: list[Mapping[str, Any]] | None,
    promotion_decision: Any = None,
) -> dict[str, Any]:
    selected = _safe_dict(selected_record)
    decision = _promotion_decision_payload(promotion_decision)
    approved = _safe_bool(selected) and _safe_bool(decision.get('approved', bool(selected)))
    top_score = 0.0
    if ranked_candidates:
        first = dict(ranked_candidates[0])
        top_score = _safe_float(first.get('goal_score'))
    summary = 'selected_promotable_run' if approved else 'no_promotable_run_selected'
    return canonical_governance_decision(
        decision_type='select_baseline',
        baseline_name=baseline_name,
        candidate_run_id=_text(selected.get('run_id')),
        selected_run_id=_text(selected.get('run_id')),
        approved=approved,
        confidence=top_score,
        reasons=decision.get('reasons') or ([] if approved else ['no_promotable_run_selected']),
        summary=summary,
        promotion_decision=decision,
        ranked_candidates=ranked_candidates,
        metadata={'selected_goal': _text(selected.get('goal'))} if selected else {},
    )


def canonical_promotion_decision(
    *,
    baseline_name: str,
    candidate_record: Mapping[str, Any] | None,
    label: str,
    fit_report: Any = None,
    governance_evidence: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    candidate = _safe_dict(candidate_record)
    fit_payload = _fit_report_payload(fit_report)
    approved = _safe_bool(fit_payload.get('approved')) if fit_payload else True
    confidence = _safe_float(fit_payload.get('score')) if fit_payload else _safe_float(dict(candidate.get('final_feedback') or {}).get('goal_score'))
    return canonical_governance_decision(
        decision_type='promote_baseline',
        baseline_name=baseline_name,
        candidate_run_id=_text(candidate.get('run_id')),
        selected_run_id=_text(candidate.get('run_id')),
        approved=approved,
        confidence=confidence,
        reasons=fit_payload.get('reasons') or ['promotion_recorded'],
        summary='baseline_promotion_recorded',
        fit_report=fit_payload,
        governance_evidence=governance_evidence,
        metadata={**_safe_dict(metadata), 'label': _text(label)},
    )


def canonical_rollback_recommendation_decision(
    *,
    baseline_name: str,
    candidate_run_id: str,
    recommendation: Mapping[str, Any] | Any,
    governance_evidence: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _safe_dict(recommendation) if isinstance(recommendation, Mapping) else {
        'should_rollback': getattr(recommendation, 'should_rollback', False),
        'confidence': getattr(recommendation, 'confidence', 0.0),
        'reason': getattr(recommendation, 'reason', ''),
        'recommended_run_id': getattr(recommendation, 'recommended_run_id', ''),
    }
    reason = _text(payload.get('reason'))
    return canonical_governance_decision(
        decision_type='rollback_recommendation',
        baseline_name=baseline_name,
        candidate_run_id=_text(candidate_run_id),
        selected_run_id=_text(payload.get('recommended_run_id')),
        approved=_safe_bool(payload.get('should_rollback')),
        confidence=_safe_float(payload.get('confidence')),
        reasons=[reason] if reason else [],
        summary='rollback_recommended' if _safe_bool(payload.get('should_rollback')) else 'rollback_not_recommended',
        governance_evidence=governance_evidence,
        metadata=metadata,
    )


__all__ = [
    'CANON_GOVERNANCE_DECISION_CONTRACT',
    'canonical_baseline_selection_decision',
    'canonical_governance_decision',
    'canonical_promotion_decision',
    'canonical_rollback_recommendation_decision',
]
