from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
from runtime.actions import ACTION_AI_CEO_PLAN_V1
from runtime.decisioning import DecisionRoute, DecisionRouteViolation, extract_strict_route_from_envelope

EXPECTED_ACTION = ACTION_AI_CEO_PLAN_V1

@dataclass(frozen=True)
class AICeoPlanRequest:
    tenant_id: str
    objective: str
    horizon: str
    route: DecisionRoute

def extract_ai_ceo_plan_request(*, payload: Dict[str, Any], env: Any) -> AICeoPlanRequest:
    route = extract_strict_route_from_envelope(payload=payload, env=env)
    route.validate(expected_action=EXPECTED_ACTION)
    p = payload or {}
    tenant_id = str(p.get("tenant_id") or getattr(getattr(env, "decision", None), "tenant_id", "") or "").strip()
    objective = str(p.get("objective") or "growth").strip()
    horizon = str(p.get("horizon") or "30d").strip()
    if not tenant_id:
        raise DecisionRouteViolation("tenant_id is required")
    return AICeoPlanRequest(tenant_id, objective, horizon, route)
