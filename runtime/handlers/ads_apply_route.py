from __future__ import annotations

from dataclasses import dataclass

from runtime.actions import ACTION_ADS_APPLY_EXECUTE_V1
from runtime.decisioning import (
    DecisionRouteViolation,
    extract_strict_route_from_envelope,
)

EXPECTED_ACTION = ACTION_ADS_APPLY_EXECUTE_V1
CANONICAL_ROUTE_MARKER = "DecisionCore->RuntimeExecutor->AdsApplyHandler"
AutopilotApplyRouteViolation = DecisionRouteViolation

@dataclass(frozen=True)
class AdsApplyRoute:
    decision_id: str
    correlation_id: str
    issuer_id: str
    action: str
    route: str

def extract_ads_apply_route(*, payload, env) -> AdsApplyRoute:
    route = extract_strict_route_from_envelope(payload=payload, env=env)
    route.validate(expected_action=EXPECTED_ACTION)
    return AdsApplyRoute(
        decision_id=route.decision_id,
        correlation_id=route.correlation_id,
        issuer_id=route.issuer_id,
        action=route.action,
        route=CANONICAL_ROUTE_MARKER,
    )
