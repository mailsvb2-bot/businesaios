from __future__ import annotations
from dataclasses import dataclass

CANON_HEADLESS_RETRY_TAXONOMY = True

@dataclass(frozen=True)
class RetryClassification:
    kind: str
    should_retry: bool
    reason: str

@dataclass(frozen=True)
class RetryTaxonomy:
    """Conservative operational retry classifier."""

    def classify(self, *, ok: bool, error: str | None) -> RetryClassification:
        if ok:
            return RetryClassification(kind="success", should_retry=False, reason="execution_ok")
        err = str(error or "").strip().lower()
        if not err:
            return RetryClassification(kind="non_recoverable", should_retry=False, reason="unknown_error")
        recoverable_markers = ("timeout", "temporarily_unavailable", "temporarily unavailable", "rate_limit", "connection_reset", "network_error", "transient")
        operator_markers = ("manual_review", "operator_required", "approval_required", "human_required", "compliance_hold")
        if any(marker in err for marker in operator_markers):
            return RetryClassification(kind="operator_required", should_retry=False, reason=err)
        if any(marker in err for marker in recoverable_markers):
            return RetryClassification(kind="recoverable", should_retry=True, reason=err)
        return RetryClassification(kind="non_recoverable", should_retry=False, reason=err)

__all__ = ["CANON_HEADLESS_RETRY_TAXONOMY", "RetryClassification", "RetryTaxonomy"]
