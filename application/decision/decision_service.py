from __future__ import annotations

from dataclasses import dataclass

from application.decision.action_dispatcher import ActionDispatcher
from application.decision.decision_contract import (
    NON_SOVEREIGN_ENGINE_ROLE,
    build_executable_action,
    canonical_request,
    start_trace,
)
from application.decision.ports import DecisionExecutionPortProtocol, ObservabilityPortProtocol
from core.constraints.decision import DecisionConstraints
from core.policy.decision_history import DecisionHistory
from core.policy.decision_publisher import DecisionPublisher
from core.policy.decision_space_narrowing_audit import DecisionSpaceNarrowingAudit
from core.policy.decision_validator import DecisionValidator
from core.scorers.selector import DecisionSelector
from kernel.decision_reason import DecisionReason
from kernel.decision_rejection import DecisionRejection
from kernel.decision_request import DecisionRequest
from kernel.decision_result import DecisionResult
from kernel.decision_space import DecisionSpace

CANON_NON_SOVEREIGN_DECISION_SERVICE = True
CANON_DECISION_SERVICE_SELECTION_ONLY = True


@dataclass(frozen=True)
class DecisionApplicationService:
    decision_execution_port: DecisionExecutionPortProtocol
    observability_port: ObservabilityPortProtocol

    def execute_action(self, action: object) -> dict:
        dispatcher = ActionDispatcher(decision_execution_port=self.decision_execution_port)
        return dispatcher.dispatch(action)

    def startup_audit_events(self) -> tuple[str, ...]:
        return self.observability_port.audit_events()


class DecisionService:
    """Neutral application service for recommendation-space selection.

    This is intentionally *not* a sovereign decision issuer. It evaluates a decision
    space and emits validated executable action DTOs, while the only sovereign
    decision entrypoint remains ``core.ai.decision_core.DecisionCore.decide``.
    """

    IS_NON_SOVEREIGN = True
    OWNS_ONLY_SELECTION = True

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
        request = canonical_request(constraints=constraints, request=request)
        audit = DecisionSpaceNarrowingAudit()
        viable = []
        trace = start_trace(request=request, candidate_count=len(space.candidates))
        for candidate in space.viable():
            candidate_issues = candidate.validate()
            if candidate_issues:
                for issue in candidate_issues:
                    audit.record(candidate.action_type or '<missing>', issue)
                continue
            ok, reason = self._validator.validate(candidate, constraints)
            if ok:
                viable.append(candidate)
            else:
                audit.record(candidate.action_type, reason)
        trace.steps.append('decision_space_validated')
        selected = self._selector.select(viable)
        if selected is None:
            trace.steps.append('decision_rejected')
            result = DecisionResult(
                candidate=None,
                reasons=[DecisionReason(code='no_viable_candidate', message='No candidate survived validation.')],
                rejection=DecisionRejection(
                    reason_code='empty_space',
                    message='Decision space is empty after validation.',
                ),
                trace=trace,
            )
        else:
            action = build_executable_action(
                candidate=selected,
                trace=trace,
                request=request,
                constraints=constraints,
            )
            trace.steps.append('executable_action_emitted')
            result = DecisionResult(
                candidate=selected,
                reasons=[DecisionReason(code='selected', message=f'Selected {selected.action_type} on {selected.channel}')],
                trace=trace,
                executable_action=action,
            )
        self._history.append(result)
        self._publisher.publish(result)
        return result, audit

    def issue(
        self,
        space: DecisionSpace,
        constraints: DecisionConstraints,
        request: DecisionRequest | None = None,
    ) -> tuple[DecisionResult, DecisionSpaceNarrowingAudit]:
        return self.select_action(space, constraints, request)

    def optimize(
        self,
        space: DecisionSpace,
        constraints: DecisionConstraints,
        request: DecisionRequest | None = None,
    ) -> tuple[DecisionResult, DecisionSpaceNarrowingAudit]:
        return self.select_action(space, constraints, request)


__all__ = [
    'CANON_DECISION_SERVICE_SELECTION_ONLY',
    'CANON_NON_SOVEREIGN_DECISION_SERVICE',
    'DecisionApplicationService',
    'DecisionService',
    'NON_SOVEREIGN_ENGINE_ROLE',
]
