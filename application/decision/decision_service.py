from __future__ import annotations

from dataclasses import dataclass

from application.decision.action_dispatcher import ActionDispatcher
from application.decision.decision_contract import (
    NON_SOVEREIGN_ENGINE_ROLE,
    canonical_request,
    start_trace,
)
from application.decision.ports import (
    DecisionExecutionPortProtocol,
    ObservabilityPortProtocol,
)
from core.constraints.decision import DecisionConstraints
from core.policy.decision_history import DecisionHistory
from core.policy.decision_publisher import DecisionPublisher
from core.policy.decision_space_narrowing_audit import (
    DecisionSpaceNarrowingAudit,
)
from core.policy.decision_validator import DecisionValidator
from core.scorers.selector import DecisionSelector
from kernel.decision_reason import DecisionReason
from kernel.decision_rejection import DecisionRejection
from kernel.decision_request import DecisionRequest
from kernel.decision_result import DecisionResult
from kernel.decision_space import DecisionSpace

CANON_NON_SOVEREIGN_DECISION_SERVICE = True
CANON_DECISION_SERVICE_SELECTION_ONLY = True
CANON_DECISION_SERVICE_NO_ISSUE_ALIASES = True
CANON_DECISION_SERVICE_NO_EXECUTABLE_ACTION = True


@dataclass(frozen=True)
class DecisionApplicationService:
    decision_execution_port: DecisionExecutionPortProtocol
    observability_port: ObservabilityPortProtocol

    def execute_envelope(self, envelope: object):
        """Execute only an already-issued canonical DecisionEnvelope."""

        dispatcher = ActionDispatcher(
            decision_execution_port=self.decision_execution_port
        )
        return dispatcher.dispatch(envelope)

    def execute_action(self, action: object):
        """Compatibility name with fail-closed envelope-only semantics."""

        return self.execute_envelope(action)

    def startup_audit_events(self) -> tuple[str, ...]:
        return self.observability_port.audit_events()


class DecisionService:
    """Recommendation-space narrowing with no decision issuance authority.

    The service can validate, rank, explain, publish, and retain a recommendation.
    It never signs a decision, creates an executable action, or invokes runtime
    execution. Final action ownership remains exclusively in ``DecisionCore``.
    """

    IS_NON_SOVEREIGN = True
    OWNS_ONLY_SELECTION = True
    PRODUCES_EXECUTABLE_ACTION = False

    def __init__(
        self,
        selector: DecisionSelector,
        validator: DecisionValidator,
        publisher: DecisionPublisher,
        history: DecisionHistory,
    ) -> None:
        self._selector = selector
        self._validator = validator
        self._publisher = publisher
        self._history = history

    def select_action(
        self,
        space: DecisionSpace,
        constraints: DecisionConstraints,
        request: DecisionRequest | None = None,
    ) -> tuple[DecisionResult, DecisionSpaceNarrowingAudit]:
        constraints.validate()
        request = canonical_request(
            constraints=constraints,
            request=request,
        )
        audit = DecisionSpaceNarrowingAudit()
        viable = []
        trace = start_trace(
            request=request,
            candidate_count=len(space.candidates),
        )
        for candidate in space.viable():
            candidate_issues = candidate.validate()
            if candidate_issues:
                for issue in candidate_issues:
                    audit.record(
                        candidate.action_type or "<missing>",
                        issue,
                    )
                continue
            ok, reason = self._validator.validate(candidate, constraints)
            if ok:
                viable.append(candidate)
            else:
                audit.record(candidate.action_type, reason)
        trace.steps.append("decision_space_validated")
        selected = self._selector.select(viable)
        if selected is None:
            trace.steps.append("recommendation_rejected")
            result = DecisionResult(
                candidate=None,
                reasons=[
                    DecisionReason(
                        code="no_viable_candidate",
                        message="No candidate survived validation.",
                    )
                ],
                rejection=DecisionRejection(
                    reason_code="empty_space",
                    message="Decision space is empty after validation.",
                ),
                trace=trace,
            )
        else:
            trace.steps.append("recommendation_emitted")
            result = DecisionResult(
                candidate=selected,
                reasons=[
                    DecisionReason(
                        code="recommended",
                        message=(
                            f"Recommended {selected.action_type} "
                            f"on {selected.channel}"
                        ),
                    )
                ],
                trace=trace,
                executable_action=None,
            )
        self._history.append(result)
        self._publisher.publish(result)
        return result, audit


__all__ = [
    "CANON_DECISION_SERVICE_NO_EXECUTABLE_ACTION",
    "CANON_DECISION_SERVICE_NO_ISSUE_ALIASES",
    "CANON_DECISION_SERVICE_SELECTION_ONLY",
    "CANON_NON_SOVEREIGN_DECISION_SERVICE",
    "DecisionApplicationService",
    "DecisionService",
    "NON_SOVEREIGN_ENGINE_ROLE",
]
