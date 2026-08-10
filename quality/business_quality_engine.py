from __future__ import annotations

from quality.business_quality_snapshot import BusinessQualitySnapshot
from quality.complaint_penalty_engine import ComplaintPenaltyEngine
from quality.customer_satisfaction_tracker import CustomerSatisfactionTracker
from quality.fraud_risk_tracker import FraudRiskTracker
from quality.no_response_penalty_engine import NoResponsePenaltyEngine
from quality.refund_quality_tracker import RefundQualityTracker
from quality.repeat_customer_tracker import RepeatCustomerTracker


class BusinessQualityEngine:
    def __init__(self) -> None:
        self._csat = CustomerSatisfactionTracker()
        self._refund = RefundQualityTracker()
        self._repeat = RepeatCustomerTracker()
        self._no_response = NoResponsePenaltyEngine()
        self._complaint = ComplaintPenaltyEngine()
        self._fraud = FraudRiskTracker()

    def evaluate(self, *, business_id: str, outcome: dict[str, object]) -> BusinessQualitySnapshot:
        score = self._csat.score(outcome) + self._repeat.bonus(outcome)
        score -= self._refund.penalty(outcome)
        score -= self._no_response.penalty(outcome)
        score -= self._complaint.penalty(outcome)
        score -= self._fraud.penalty(outcome)
        score = max(0.0, min(1.0, score))
        reasons = []
        if not outcome.get("responded", False):
            reasons.append("no_response")
        if outcome.get("returned"):
            reasons.append("refund")
        if outcome.get("complaint"):
            reasons.append("complaint")
        if outcome.get("fraud_flag"):
            reasons.append("fraud")
        return BusinessQualitySnapshot(str(business_id), float(score), tuple(reasons))
