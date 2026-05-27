from __future__ import annotations

from config.governance_review_policy import GovernanceReviewPolicy

from .contracts import AuditRecord


def requires_review(
    record: AuditRecord,
    threshold: float | None = None,
    *,
    policy: GovernanceReviewPolicy | None = None,
) -> bool:
    resolved_policy = policy or GovernanceReviewPolicy()
    effective_threshold = float(resolved_policy.risk_review_threshold if threshold is None else threshold)
    return record.risk_score >= effective_threshold
