from __future__ import annotations

from guardrails._shared import GuardCheckResult, _as_float, _payload_view


class RiskScoreGuard:
    def __init__(self, *, block_threshold: float = 0.8, review_threshold: float = 0.5) -> None:
        self._block_threshold = float(block_threshold)
        self._review_threshold = float(review_threshold)

    def check(self, payload: dict) -> tuple[bool, str]:
        body = _payload_view(payload)
        risk_score = _as_float(body.get('risk_score', 0.0), minimum=0.0, maximum=1.0)
        if risk_score >= self._block_threshold:
            return GuardCheckResult(False, 'risk_score_blocked').as_tuple()
        if risk_score >= self._review_threshold:
            return GuardCheckResult(False, 'risk_score_review_required').as_tuple()
        return GuardCheckResult(True, 'risk_score_ok').as_tuple()
