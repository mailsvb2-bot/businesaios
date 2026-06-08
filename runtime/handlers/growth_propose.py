from __future__ import annotations

CANON_THIN_HANDLER = True

from typing import Any

from runtime.actions import ACTION_GROWTH_PROPOSE_V1
from runtime.decisioning import DecisionRouteViolation, extract_strict_route_from_envelope
from runtime.handlers.route_failure_support import best_effort_route_ids, blocked_error_payload, safe_route_blocked_text
from runtime.ports.effects import EffectsPort

ACTION_NAME = ACTION_GROWTH_PROPOSE_V1

def handle_growth_propose(payload: dict[str, Any], effects: EffectsPort, env: Any, *, proposal_service: Any, proposal_gateway: Any) -> Any:
    p = payload or {}
    try:
        route = extract_strict_route_from_envelope(payload=p, env=env)
        route.validate(expected_action=ACTION_NAME)
    except DecisionRouteViolation as exc:
        fallback_decision_id, fallback_correlation_id = best_effort_route_ids(payload=p, env=env)
        return effects.send_message(decision_id=fallback_decision_id, correlation_id=fallback_correlation_id, user_id=str(p.get("user_id") or ""), text=safe_route_blocked_text("Growth propose"), track_event_type="growth_propose_blocked@v1", track_payload=blocked_error_payload(reason="route_violation", exc=exc))
    if proposal_service is None or proposal_gateway is None:
        return effects.send_message(decision_id=route.decision_id, correlation_id=route.correlation_id, user_id=str(p.get("user_id") or ""), text="🛑 Growth proposal wiring missing.", track_event_type="growth_propose_blocked@v1", track_payload={"error": "proposal_wiring_missing"})
    try:
        tenant_id = str(p.get("tenant_id") or "").strip()
        if not tenant_id:
            raise DecisionRouteViolation("tenant_id is required")
        proposals = proposal_service.build_proposals(tenant_id=tenant_id, objective=str(p.get("objective") or "growth").strip(), signals=dict(p.get("signals") or {}))
        queued = proposal_service.queue(gateway=proposal_gateway, tenant_id=tenant_id, decision_id=route.decision_id, correlation_id=route.correlation_id, issuer_id=route.issuer_id, proposals=proposals)
        return effects.send_message(decision_id=route.decision_id, correlation_id=route.correlation_id, user_id=str(p.get("user_id") or ""), text=f"📦 Growth proposals queued: {queued}", track_event_type=ACTION_NAME, track_payload={"queued": queued})
    except DecisionRouteViolation as exc:
        return effects.send_message(decision_id=route.decision_id, correlation_id=route.correlation_id, user_id=str(p.get("user_id") or ""), text=safe_route_blocked_text("Growth propose"), track_event_type="growth_propose_blocked@v1", track_payload=blocked_error_payload(reason="route_violation", exc=exc))
