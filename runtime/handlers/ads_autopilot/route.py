from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.actions import ACTION_ADS_AUTOPILOT_TICK_V1
from runtime.decisioning import (
    DecisionRouteViolation,
    canonical_runtime_route,
    extract_strict_route_from_envelope,
)

_EXPECTED_ACTION = ACTION_ADS_AUTOPILOT_TICK_V1
CANONICAL_ROUTE_MARKER = "DecisionCore->RuntimeExecutor->AdsAutopilotHandler"

class AutopilotRouteViolation(DecisionRouteViolation):
    pass

@dataclass(frozen=True)
class AutopilotRoute:
    decision_id: str
    correlation_id: str
    issuer_id: str
    issued_action: str
    route: str

def extract_autopilot_route(*, payload: dict[str, Any], env: Any) -> AutopilotRoute:
    try:
        route = extract_strict_route_from_envelope(payload=payload, env=env)
        route.validate(expected_action=_EXPECTED_ACTION)
    except DecisionRouteViolation as exc:
        raise AutopilotRouteViolation(str(exc)) from exc
    return AutopilotRoute(
        route.decision_id,
        route.correlation_id,
        route.issuer_id,
        route.action,
        CANONICAL_ROUTE_MARKER,
    )
