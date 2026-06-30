from __future__ import annotations

from runtime.human_governance import ReviewCase, build_runtime_review_case

CANON_THIN_HANDLER = True

def handle_human_governance_build(subject_id: str, reason: str) -> ReviewCase:
    return build_runtime_review_case(subject_id=subject_id, reason=reason)
