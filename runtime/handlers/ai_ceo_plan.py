from __future__ import annotations

from typing import Any
from runtime.actions import ACTION_AI_CEO_PLAN_V1
from runtime.ai_ceo import render_plan_text
from runtime.decisioning import DecisionRouteViolation
from runtime.handlers.ai_ceo_plan_flow import extract_ai_ceo_plan_request
from runtime.handlers.route_failure_support import (
    best_effort_route_ids as _best_effort_route_ids,
)
from runtime.handlers.route_failure_support import (
    blocked_error_payload,
    safe_route_blocked_text,
    safe_runtime_error_text,
)
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True
ACTION_NAME = ACTION_AI_CEO_PLAN_V1

def handle_ai_ceo_plan(payload: dict[str, Any], effects: EffectsPort, env: Any, *, planner: Any) -> Any:
    p = payload or {}
    try:
        req = extract_ai_ceo_plan_request(payload=p, env=env)
    except DecisionRouteViolation as exc:
        fallback_decision_id, fallback_correlation_id = _best_effort_route_ids(payload=p, env=env)
        return effects.send_message(
            decision_id=fallback_decision_id,
            correlation_id=fallback_correlation_id,
            user_id=str(p.get('user_id') or ''),
            text=safe_route_blocked_text('AI CEO'),
            track_event_type='ai_ceo_plan_blocked@v1',
            track_payload=blocked_error_payload(reason='route_violation', exc=exc),
        )
    if planner is None:
        raise RuntimeError("boot failure: AI CEO planner must be wired before handler dispatch")
    build_plan = getattr(planner, "build_plan", None)
    if not callable(build_plan):
        raise RuntimeError("boot failure: AI CEO planner must expose build_plan")
    try:
        plan = build_plan(
            tenant_id=req.tenant_id,
            objective=req.objective,
            horizon=req.horizon,
            decision_id=req.route.decision_id,
            correlation_id=req.route.correlation_id,
        )
        return effects.send_message(
            decision_id=req.route.decision_id,
            correlation_id=req.route.correlation_id,
            user_id=str(p.get('user_id') or ''),
            text=_format_plan(plan),
            track_event_type=ACTION_NAME,
            track_payload={'status': 'ok', 'tenant_id': req.tenant_id},
        )
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        return effects.send_message(
            decision_id=req.route.decision_id,
            correlation_id=req.route.correlation_id,
            user_id=str(p.get('user_id') or ''),
            text=safe_runtime_error_text('AI CEO plan'),
            track_event_type='ai_ceo_plan_error@v1',
            track_payload=blocked_error_payload(reason='planner_error', exc=exc),
        )


def _format_plan(plan: Any) -> str:
    if hasattr(plan, 'steps') and hasattr(plan, 'intent') and hasattr(plan, 'summary'):
        return render_plan_text(plan)
    if isinstance(plan, dict):
        return '🧠 AI CEO Plan\n' + f"steps: {len(plan.get('steps') or [])}"
    return '🧠 AI CEO Plan ready'
