from __future__ import annotations

from datetime import UTC, datetime

from core.human_governance.contracts import ReviewCase
from core.human_governance.explainers.review_case_explainer import explain_review_case
from core.human_governance.types import ReviewItem

CANON_RUNTIME_HUMAN_GOVERNANCE_PUBLIC_API = True


def build_runtime_review_case(subject_id: str, reason: str) -> ReviewCase:
    review = ReviewItem(
        review_id=f"review:{str(subject_id)}",
        decision_id="",
        subject_type="subject",
        subject_id=str(subject_id),
        reason=str(reason),
        risk_level="low",
        status="pending",
        requested_by="runtime",
        requested_at=datetime.now(UTC),
    )
    return ReviewCase(review=review, state=None, need_approval=False, escalation_risk=0.0, notes=())


__all__ = [
    'CANON_RUNTIME_HUMAN_GOVERNANCE_NAMESPACE',
    'CANON_RUNTIME_HUMAN_GOVERNANCE_PUBLIC_API',
    'ReviewCase',
    'build_runtime_review_case',
    'explain_review_case',
]

CANON_RUNTIME_HUMAN_GOVERNANCE_NAMESPACE = True



