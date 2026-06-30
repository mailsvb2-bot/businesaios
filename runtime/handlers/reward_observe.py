from __future__ import annotations

from typing import Any
from runtime.actions import ACTION_REWARD_OBSERVE_V1
from runtime.decisioning import DecisionRouteViolation, extract_strict_route_from_envelope
from runtime.handlers.route_failure_support import best_effort_route_ids, blocked_error_payload, safe_route_blocked_text
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True
ACTION_NAME = ACTION_REWARD_OBSERVE_V1

def handle_reward_observe(payload: dict[str, Any], effects: EffectsPort, env: Any, *, observer: Any) -> Any:
    p = payload or {}
    try:
        route = extract_strict_route_from_envelope(payload=p, env=env)
        route.validate(expected_action=ACTION_NAME)
    except DecisionRouteViolation as exc:
        fallback_decision_id, fallback_correlation_id = best_effort_route_ids(payload=p, env=env)
        return effects.send_message(decision_id=fallback_decision_id, correlation_id=fallback_correlation_id, user_id=str(p.get("user_id") or ""), text=safe_route_blocked_text("Reward observe"), track_event_type="reward_observe_blocked@v1", track_payload=blocked_error_payload(reason="route_violation", exc=exc))
    if observer is None:
        raise RuntimeError("boot failure: reward observer must be wired before handler dispatch")
    try:
        tenant_id = str(p.get("tenant_id") or "").strip()
        if not tenant_id:
            raise DecisionRouteViolation("tenant_id is required")
        obs = observer.observe(tenant_id=tenant_id, metrics=dict(p.get("metrics") or {}), context={"decision_id": route.decision_id, "correlation_id": route.correlation_id, "issuer_id": route.issuer_id})
        return effects.send_message(decision_id=route.decision_id, correlation_id=route.correlation_id, user_id=str(p.get("user_id") or ""), text=f"📈 Reward observed: {obs.get('reward')}", track_event_type=ACTION_NAME, track_payload={"reward": obs.get("reward")})
    except DecisionRouteViolation as exc:
        return effects.send_message(decision_id=route.decision_id, correlation_id=route.correlation_id, user_id=str(p.get("user_id") or ""), text=safe_route_blocked_text("Reward observe"), track_event_type="reward_observe_blocked@v1", track_payload=blocked_error_payload(reason="route_violation", exc=exc))
