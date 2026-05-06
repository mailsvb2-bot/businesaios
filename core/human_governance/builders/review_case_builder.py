from __future__ import annotations

from ..contracts import ApprovalStateReader, HumanGovernancePolicyContract
from ..evaluators.approval_need_evaluator import ApprovalNeedEvaluator
from ..evaluators.escalation_risk_evaluator import EscalationRiskEvaluator
from ..types import ReviewCase, ReviewItem


class ReviewCaseBuilder:
    def __init__(
        self,
        approval_state_reader: ApprovalStateReader,
        policy: HumanGovernancePolicyContract,
    ) -> None:
        self._approval_state_reader = approval_state_reader
        self._approval_need_evaluator = ApprovalNeedEvaluator(policy=policy)
        self._escalation_risk_evaluator = EscalationRiskEvaluator()

    def build(self, review: ReviewItem) -> ReviewCase:
        state = self._approval_state_reader.read_state(review.review_id)
        need_approval = self._approval_need_evaluator.evaluate(review, state)
        escalation_risk = self._escalation_risk_evaluator.evaluate(review, state)

        notes: list[str] = []
        if need_approval:
            notes.append("human approval required")
        if escalation_risk >= 0.75:
            notes.append("high escalation risk")

        return ReviewCase(
            review=review,
            state=state,
            need_approval=need_approval,
            escalation_risk=escalation_risk,
            notes=tuple(notes),
        )
