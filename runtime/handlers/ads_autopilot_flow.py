from __future__ import annotations

from runtime.decisioning import DecisionCommand, RecommendationSet
from runtime.execution.decision_execution_service import (
    DecisionExecutionService,
    build_bound_decision_execution_service,
    validate_and_run_decision_command,
)
from runtime.handlers.ads_autopilot import (
    AutopilotRoute,
    AutopilotRouteViolation,
    ensure_autopilot_gate,
    extract_autopilot_route,
    format_autopilot_result,
    gate_error_text,
)

CANON_THIN_HANDLER = True
CANON_ADS_AUTOPILOT_EXECUTION_THIN_BOUNDARY = True
CANON_ADS_AUTOPILOT_EXECUTION_SHARED_OWNER = True
# build_decision_execution_service(



def handle_ads_autopilot_proposal(
    recommendations: RecommendationSet,
) -> RecommendationSet:
    """Thin boundary function for proposal stage.
    No execution. No hidden selection.
    """
    return recommendations


def handle_ads_autopilot_execution(
    service: DecisionExecutionService,
    command: DecisionCommand,
) -> object:
    """Thin execution boundary.
    Requires validated DecisionCommand from central decision layer.
    """
    return validate_and_run_decision_command(service=service, command=command)


def build_ads_autopilot_execution_service(*, executor: object, keyring: object | None = None) -> DecisionExecutionService:
    if keyring is None:
        return DecisionExecutionService(executor=executor, keyring=keyring)
    return build_bound_decision_execution_service(executor=executor, keyring=keyring)



__all__ = [
    "AutopilotRoute",
    "AutopilotRouteViolation",
    "ensure_autopilot_gate",
    "extract_autopilot_route",
    "format_autopilot_result",
    "gate_error_text",
    "build_ads_autopilot_execution_service",
    "handle_ads_autopilot_execution",
    "handle_ads_autopilot_proposal",
]
