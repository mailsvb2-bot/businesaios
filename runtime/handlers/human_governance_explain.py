from __future__ import annotations

from runtime.human_governance import ReviewCase, explain_review_case

CANON_THIN_HANDLER = True

def handle_human_governance_explain(case: ReviewCase) -> str:
    return explain_review_case(case)
