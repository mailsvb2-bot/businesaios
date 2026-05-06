from __future__ import annotations

CANON_THIN_HANDLER = True

from runtime.human_governance import ReviewCase, build_runtime_review_case

def handle_human_governance_build(subject_id: str, reason: str) -> ReviewCase:
    return build_runtime_review_case(subject_id=subject_id, reason=reason)
