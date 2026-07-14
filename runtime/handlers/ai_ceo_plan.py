from __future__ import annotations

from collections.abc import Mapping
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


def _delivery_evidence(delivery: object) -> dict[str, Any] | None:
    if not isinstance(delivery, Mapping):
        return None
    for key in ("router_evidence", "evidence", "verification"):
        candidate = delivery.get(key)
        if isinstance(candidate, Mapping) and str(candidate.get("source") or "").strip():
            return dict(candidate)
    return None


def _failed_delivery(*, delivery: Any, reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "blocked" if reason == "route_violation" else "failed",
        "reason": str(reason),
        "delivery": delivery,
        "router_evidence": None,
    }


def handle_ai_ceo_plan(payload: dict[str, Any], effects: EffectsPort, env: Any, *, planner: Any) -> Any:
    body = dict(payload or {})
    tenant_id = str(body.get("tenant_id") or "").strip()
    user_id = str(body.get("user_id") or "").strip()
    try:
        request = extract_ai_ceo_plan_request(payload=body, env=env)
    except DecisionRouteViolation as exc:
        fallback_decision_id, fallback_correlation_id = _best_effort_route_ids(
            payload=body,
            env=env,
        )
        delivery = effects.send_message(
            decision_id=fallback_decision_id,
            correlation_id=fallback_correlation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            text=safe_route_blocked_text("AI CEO"),
            track_event_type="ai_ceo_plan_blocked@v1",
            track_payload=blocked_error_payload(
                reason="route_violation",
                exc=exc,
            ),
        )
        return _failed_delivery(delivery=delivery, reason="route_violation")

    if planner is None:
        raise RuntimeError("boot failure: AI CEO planner must be wired before handler dispatch")
    build_plan = getattr(planner, "build_plan", None)
    if not callable(build_plan):
        raise RuntimeError("boot failure: AI CEO planner must expose build_plan")

    try:
        plan = build_plan(
            tenant_id=request.tenant_id,
            objective=request.objective,
            horizon=request.horizon,
            decision_id=request.route.decision_id,
            correlation_id=request.route.correlation_id,
        )
        delivery = effects.send_message(
            decision_id=request.route.decision_id,
            correlation_id=request.route.correlation_id,
            tenant_id=request.tenant_id,
            user_id=user_id,
            text=_format_plan(plan),
            track_event_type=ACTION_NAME,
            track_payload={
                "status": "ok",
                "tenant_id": request.tenant_id,
            },
        )
        evidence = _delivery_evidence(delivery)
        delivery_ok = bool(delivery.get("ok")) if isinstance(delivery, Mapping) else bool(delivery)
        verified = bool(delivery_ok and evidence)
        return {
            "ok": verified,
            "status": "verified" if verified else "failed",
            "plan": plan,
            "delivery": delivery,
            "router_evidence": evidence if verified else None,
        }
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        delivery = effects.send_message(
            decision_id=request.route.decision_id,
            correlation_id=request.route.correlation_id,
            tenant_id=request.tenant_id,
            user_id=user_id,
            text=safe_runtime_error_text("AI CEO plan"),
            track_event_type="ai_ceo_plan_error@v1",
            track_payload=blocked_error_payload(
                reason="planner_error",
                exc=exc,
            ),
        )
        return _failed_delivery(delivery=delivery, reason="planner_error")


def _format_plan(plan: Any) -> str:
    if hasattr(plan, "steps") and hasattr(plan, "intent") and hasattr(plan, "summary"):
        return render_plan_text(plan)
    if isinstance(plan, dict):
        return "🧠 AI CEO Plan\n" + f"steps: {len(plan.get('steps') or [])}"
    return "🧠 AI CEO Plan ready"
