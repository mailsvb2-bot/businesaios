from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
CANON_VERIFICATION_METRICS = True
@dataclass(frozen=True, slots=True)
class VerificationMetrics:
    total_verifications: int
    verified_count: int
    failed_count: int
    delayed_count: int
    timed_out_count: int
    conflicted_count: int
    retryable_count: int
    authoritative_success_count: int
    average_confidence: float
    def to_dict(self) -> dict[str, float | int]:
        return {
            "total_verifications": self.total_verifications,
            "verified_count": self.verified_count,
            "failed_count": self.failed_count,
            "delayed_count": self.delayed_count,
            "timed_out_count": self.timed_out_count,
            "conflicted_count": self.conflicted_count,
            "retryable_count": self.retryable_count,
            "authoritative_success_count": self.authoritative_success_count,
            "average_confidence": float(self.average_confidence),
        }
def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}
class VerificationMetricsCollector:
    def summarize(self, decisions: list[dict] | tuple[dict, ...]) -> VerificationMetrics:
        rows = [_safe_dict(item) for item in decisions]
        total = len(rows)
        if total == 0:
            return VerificationMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0.0)
        verified_count = sum(1 for item in rows if bool(item.get("verified")))
        delayed_count = sum(1 for item in rows if bool(item.get("delayed")))
        timed_out_count = sum(1 for item in rows if bool(item.get("timed_out")))
        conflicted_count = sum(1 for item in rows if bool(item.get("conflicting_evidence_ids")))
        retryable_count = sum(1 for item in rows if bool(item.get("retryable")))
        authoritative_success_count = sum(
            1
            for item in rows
            if bool(item.get("verified"))
            and int(len(item.get("matched_evidence_ids") or [])) > 0
            and str(item.get("source_of_truth") or "").strip() not in {"", "none"}
        )
        failed_count = total - verified_count
        average_confidence = sum(float(item.get("confidence") or 0.0) for item in rows) / total
        return VerificationMetrics(
            total_verifications=total,
            verified_count=verified_count,
            failed_count=failed_count,
            delayed_count=delayed_count,
            timed_out_count=timed_out_count,
            conflicted_count=conflicted_count,
            retryable_count=retryable_count,
            authoritative_success_count=authoritative_success_count,
            average_confidence=average_confidence,
        )
__all__ = ["CANON_VERIFICATION_METRICS", "VerificationMetrics", "VerificationMetricsCollector"]
