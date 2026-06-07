from __future__ import annotations

CANON_THIN_HANDLER = True

from typing import Any

from runtime.actions import ACTION_PRICING_SELECT_V1
from runtime.decisioning import DecisionRouteViolation, extract_strict_route_from_envelope
from runtime.handlers.route_failure_support import best_effort_route_ids, blocked_error_payload, safe_route_blocked_text
from runtime.ports.effects import EffectsPort
from runtime.pricing import PricingRouteViolation, PricingSelectionContext

ACTION_NAME = ACTION_PRICING_SELECT_V1

def handle_pricing_select(payload: dict[str, Any], effects: EffectsPort, env: Any, *, selection_service: Any) -> Any:
    p = payload or {}
    try:
        route = extract_strict_route_from_envelope(payload=p, env=env)
        route.validate(expected_action=ACTION_NAME)
    except DecisionRouteViolation as exc:
        fallback_decision_id, fallback_correlation_id = best_effort_route_ids(payload=p, env=env)
        return effects.send_message(
            decision_id=fallback_decision_id,
            correlation_id=fallback_correlation_id,
            user_id=str(p.get("user_id") or ""),
            text=safe_route_blocked_text("Pricing"),
            track_event_type="pricing_select_blocked@v1",
            track_payload=blocked_error_payload(reason="route_violation", exc=exc),
        )
    if selection_service is None:
        raise RuntimeError("boot failure: pricing selection_service must be wired before handler dispatch")
    try:
        ctx = PricingSelectionContext(tenant_id=str(p.get("tenant_id") or ""), decision_id=route.decision_id, correlation_id=route.correlation_id, issuer_id=route.issuer_id, action=route.action)
        result = selection_service.select(ctx=ctx, candidates=list(p.get("candidates") or []), evidence=dict(p.get("evidence") or {}))
        return effects.send_message(decision_id=route.decision_id, correlation_id=route.correlation_id, user_id=str(p.get("user_id") or ""), text=f"💸 Pricing selected: {bool(result.get('selected'))}", track_event_type=ACTION_NAME, track_payload={"selected": bool(result.get("selected"))})
    except PricingRouteViolation as exc:
        return effects.send_message(
            decision_id=route.decision_id,
            correlation_id=route.correlation_id,
            user_id=str(p.get("user_id") or ""),
            text=safe_route_blocked_text("Pricing"),
            track_event_type="pricing_select_blocked@v1",
            track_payload=blocked_error_payload(reason="pricing_route_violation", exc=exc),
        )
