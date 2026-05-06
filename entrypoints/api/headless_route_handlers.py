from __future__ import annotations

"""Final owner: entrypoints.api.headless_route_handlers."""

CANON_API_HEADLESS_ROUTE_HANDLERS_FINAL_OWNER = True
CANON_API_HEADLESS_ROUTE_HANDLERS_SINGLE_RUNTIME_PROVIDER = True

from dataclasses import dataclass, field

from execution.headless_boot import build_headless_runtime

from application.capability.capability_operator_view import merge_capability_views, normalize_capability_view
from application.headless.models import CEOParticipation, GoalExecutionRequest
from entrypoints.api.headless_models import (
    ExecuteGoalRequest,
    ExecuteGoalResponse,
    ExecuteGoalStepResponse,
)
from entrypoints.api.headless_runtime_provider import HeadlessRuntimeProvider, build_default_headless_runtime_provider, build_headless_runtime_provider


CANON_API_HEADLESS_ROUTE_HANDLERS_SINGLE_RUNTIME_PROVIDER = True


def _bootstrap_headless_runtime() -> object:
    return globals()["build_headless_runtime"]()


def _default_runtime_provider() -> HeadlessRuntimeProvider:
    return build_headless_runtime_provider(runtime=_bootstrap_headless_runtime())



def build_headless_route_handlers(*, runtime_provider: HeadlessRuntimeProvider | None = None) -> "HeadlessRouteHandlers":
    return HeadlessRouteHandlers(runtime_provider=runtime_provider or build_default_headless_runtime_provider())


@dataclass(frozen=True)
class HeadlessRouteHandlers:
    runtime_provider: HeadlessRuntimeProvider = field(default_factory=_default_runtime_provider)

    def execute_goal(self, request: ExecuteGoalRequest) -> ExecuteGoalResponse:
        report = self.runtime_provider.contract_runtime().execute_autopilot(
            GoalExecutionRequest(
                goal=request.goal,
                business_id=request.business_id,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                region=request.region,
                max_steps=request.max_steps,
                profile=dict(request.profile),
                signals=list(request.signals),
                constraints=dict(request.constraints),
                economy=dict(request.economy),
                meta=dict(request.meta),
                ceo=CEOParticipation(
                    enabled=bool(request.ceo.enabled),
                    objective=request.ceo.objective or request.goal,
                    horizon=request.ceo.horizon,
                    risk_level=request.ceo.risk_level,
                ),
            )
        )
        return ExecuteGoalResponse(
            goal=report.goal,
            business_id=report.business_id,
            tenant_id=report.tenant_id,
            completed=report.completed,
            stop_reason=report.stop_reason,
            steps=[
                ExecuteGoalStepResponse(
                    step_index=step.step_index,
                    decision_id=step.decision_id,
                    action_id=step.action_id,
                    action=step.action,
                    status=step.status,
                    ok=step.ok,
                    correlation_id=step.correlation_id,
                    reason=step.reason,
                    payload=dict(step.payload),
                    feedback=dict(step.feedback),
                    capability_view=merge_capability_views(step.payload, step.feedback),
                )
                for step in report.steps
            ],
            final_feedback=dict(report.final_feedback),
            capability_view=normalize_capability_view(report.final_feedback),
        )
