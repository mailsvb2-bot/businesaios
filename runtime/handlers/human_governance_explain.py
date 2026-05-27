from __future__ import annotations

CANON_THIN_HANDLER = True
from runtime.human_governance import ReviewCase, explain_review_case


def handle_human_governance_explain(case: ReviewCase) -> str:
    return explain_review_case(case)
