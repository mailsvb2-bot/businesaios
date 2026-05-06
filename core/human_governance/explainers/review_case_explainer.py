from __future__ import annotations

from ..types import ReviewCase


def explain_review_case(case: ReviewCase) -> str:
    """Explain a review case as string (handler contract)."""
    d = _explainer.explain(case)
    return "; ".join(f"{k}={v}" for k, v in d.items())


class ReviewCaseExplainer:
    def explain(self, case: ReviewCase) -> dict[str, object]:
        return {
            "review_id": case.review.review_id,
            "decision_id": case.review.decision_id,
            "status": case.review.status,
            "need_approval": case.need_approval,
            "escalation_risk": round(case.escalation_risk, 4),
            "notes": list(case.notes),
        }


_explainer = ReviewCaseExplainer()
