from __future__ import annotations

from .builders.escalation_case_builder import EscalationCaseBuilder
from .builders.override_case_builder import OverrideCaseBuilder
from .builders.review_case_builder import ReviewCaseBuilder
from .contracts import HumanGovernanceDeps
from .errors import ReviewNotFoundError
from .guards.stale_review_guard import StaleReviewGuard
from .guards.unauthorized_override_guard import UnauthorizedOverrideGuard
from .types import ApprovalDecision, ApprovalState, OverrideRecord, ReviewCase, ReviewItem


class HumanGovernanceService:
    """
    Тонкий orchestration layer.

    Не решает бизнес-вопросы сам.
    Не подменяет DecisionCore.
    Не создаёт "второй мозг".
    Только:
    - валидирует вход;
    - проверяет guard/policy;
    - вызывает маленькие зависимости.
    """

    def __init__(
        self,
        deps: HumanGovernanceDeps,
        stale_review_guard: StaleReviewGuard | None = None,
        unauthorized_override_guard: UnauthorizedOverrideGuard | None = None,
    ) -> None:
        self._deps = deps
        self._policy = deps.policy
        self._stale_review_guard = stale_review_guard or StaleReviewGuard()
        self._unauthorized_override_guard = (
            unauthorized_override_guard or UnauthorizedOverrideGuard()
        )
        self._review_case_builder = ReviewCaseBuilder(
            approval_state_reader=deps.approval_state_reader,
            policy=deps.policy,
        )
        self._override_case_builder = OverrideCaseBuilder(
            override_repository=deps.override_repository,
        )
        self._escalation_case_builder = EscalationCaseBuilder(
            escalation_reader=deps.escalation_reader,
        )

    def build_review_case(self, review_id: str) -> ReviewCase:
        review = self._require_review(review_id)
        return self._review_case_builder.build(review)

    def build_override_case(self, review_id: str) -> dict[str, object]:
        self._require_review(review_id)
        return self._override_case_builder.build(review_id)

    def build_escalation_case(self, review_id: str) -> dict[str, object]:
        self._require_review(review_id)
        return self._escalation_case_builder.build(review_id)

    def approve(self, decision: ApprovalDecision) -> ApprovalState:
        decision = self._policy.validate_approval_decision(decision)
        review = self._require_review(decision.review_id)
        self._policy.ensure_actionable(review.status)
        self._stale_review_guard.ensure_fresh(review)
        return self._deps.approval_writer.write_approval(decision)

    def reject(self, decision: ApprovalDecision) -> ApprovalState:
        decision = self._policy.validate_approval_decision(decision)
        review = self._require_review(decision.review_id)
        self._policy.ensure_actionable(review.status)
        self._stale_review_guard.ensure_fresh(review)
        return self._deps.rejection_writer.write_rejection(decision)

    def override(self, record: OverrideRecord, allowed_actor_ids: set[str]) -> OverrideRecord:
        record = self._policy.validate_override_record(record)
        review = self._require_review(record.review_id)
        self._policy.ensure_actionable(review.status)
        self._unauthorized_override_guard.ensure_allowed(
            actor_id=record.actor_id,
            allowed_actor_ids=allowed_actor_ids,
        )
        return self._deps.override_writer.write_override(record)

    def pause(self, review_id: str, reason: str, actor_id: str) -> ApprovalState:
        normalized_actor_id = self._policy.validate_actor_id(actor_id)
        normalized_reason = self._policy.validate_reason(reason)
        review = self._require_review(review_id)
        self._policy.ensure_actionable(review.status)
        return self._deps.pause_writer.write_pause(
            review_id=review_id,
            reason=normalized_reason,
            actor_id=normalized_actor_id,
        )

    def _require_review(self, review_id: str) -> ReviewItem:
        review = self._deps.review_repository.get(review_id)
        if review is None:
            raise ReviewNotFoundError(f"review '{review_id}' not found")
        return review