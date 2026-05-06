from __future__ import annotations

CANON_DEMAND_FEEDBACK_ALIAS_NAMESPACE = True

class BusinessPerformanceFeedback:
    def summarize(self, outcome: dict[str, object]) -> dict[str, object]:
        return {"responded": bool(outcome.get("responded")), "converted": bool(outcome.get("converted"))}

class CustomerOutcomeFeedback:
    def summarize(self, outcome: dict[str, object]) -> dict[str, object]:
        return {"customer_success": bool(outcome.get("converted")), "returned": bool(outcome.get("returned"))}

class FeedbackAudit:
    def record(self, payload: dict[str, object]) -> dict[str, object]:
        return {"keys": tuple(sorted(payload.keys())), "size": len(payload)}

class FeedbackMemory:
    def __init__(self, *, max_rows: int = 5000) -> None:
        self._rows: list[dict[str, object]] = []
        self._max_rows = max(1, int(max_rows))

    def append(self, payload: dict[str, object]) -> None:
        self._rows.append(dict(payload))
        if len(self._rows) > self._max_rows:
            self._rows = self._rows[-self._max_rows :]

    def rows(self) -> tuple[dict[str, object], ...]:
        return tuple(self._rows)

class FeedbackSnapshotBuilder:
    def build(self, *payloads: dict[str, object]) -> dict[str, object]:
        snapshot: dict[str, object] = {}
        for payload in payloads:
            snapshot.update(dict(payload))
        return snapshot

class MatchFeedbackEngine:
    def build_feedback(self, *, request_id: str, scores: dict[str, float], converted: bool) -> dict[str, object]:
        return {"request_id": request_id, "scores": dict(scores), "converted": bool(converted)}

class QualityFeedbackEngine:
    def summarize(self, quality_snapshot: object) -> dict[str, object]:
        return {"quality_score": float(quality_snapshot.quality_score), "reason_codes": tuple(quality_snapshot.reason_codes)}

class RevenueFeedbackEngine:
    def summarize(self, outcome: dict[str, object]) -> dict[str, object]:
        return {"revenue": float(outcome.get("revenue") or 0.0)}

class RoutingFeedbackEngine:
    def build_feedback(self, *, request_id: str, business_id: str, outcome: dict[str, object]) -> dict[str, object]:
        return {"request_id": request_id, "business_id": business_id, "outcome_code": "converted" if outcome.get("converted") else "open"}

__all__ = [
    'BusinessPerformanceFeedback',
    'CustomerOutcomeFeedback',
    'FeedbackAudit',
    'FeedbackMemory',
    'FeedbackSnapshotBuilder',
    'MatchFeedbackEngine',
    'QualityFeedbackEngine',
    'RevenueFeedbackEngine',
    'RoutingFeedbackEngine',
]
