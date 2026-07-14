from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime.actions import ACTION_REWARD_OBSERVE_V1
from runtime.decisioning import DecisionRouteViolation, extract_strict_route_from_envelope
from runtime.handlers.route_failure_support import (
    best_effort_route_ids,
    blocked_error_payload,
    safe_route_blocked_text,
)
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True
ACTION_NAME = ACTION_REWARD_OBSERVE_V1


def _delivery_evidence(delivery: object) -> dict[str, Any] | None:
    if not isinstance(delivery, Mapping):
        return None
    for key in ("router_evidence", "evidence", "verification"):
        candidate = delivery.get(key)
        if isinstance(candidate, Mapping) and str(candidate.get("source") or "").strip():
            return dict(candidate)
    return None


def _blocked(
    *,
    payload: dict[str, Any],
    effects: EffectsPort,
    decision_id: str,
    correlation_id: str,
    reason: str,
    exc: Exception,
) -> dict[str, Any]:
    delivery = effects.send_message(
        decision_id=decision_id,
        correlation_id=correlation_id,
        tenant_id=str(payload.get("tenant_id") or "").strip(),
        user_id=str(payload.get("user_id") or ""),
        text=safe_route_blocked_text("Reward observe"),
        track_event_type="reward_observe_blocked@v1",
        track_payload=blocked_error_payload(reason=reason, exc=exc),
        channel=str(payload.get("channel") or "telegram"),
        channel_policy=(
            dict(payload.get("channel_policy") or {})
            if isinstance(payload.get("channel_policy"), Mapping)
            else None
        ),
    )
    return {
        "ok": False,
        "status": "blocked",
        "reason": reason,
        "delivery": delivery,
        "router_evidence": None,
    }


def handle_reward_observe(
    payload: dict[str, Any],
    effects: EffectsPort,
    env: Any,
    *,
    observer: Any,
) -> Any:
    body = dict(payload or {})
    try:
        route = extract_strict_route_from_envelope(payload=body, env=env)
        route.validate(expected_action=ACTION_NAME)
    except DecisionRouteViolation as exc:
        decision_id, correlation_id = best_effort_route_ids(payload=body, env=env)
        return _blocked(
            payload=body,
            effects=effects,
            decision_id=decision_id,
            correlation_id=correlation_id,
            reason="route_violation",
            exc=exc,
        )

    if observer is None:
        raise RuntimeError("boot failure: reward observer must be wired before handler dispatch")

    try:
        tenant_id = str(body.get("tenant_id") or "").strip()
        user_id = str(body.get("user_id") or "").strip()
        if not tenant_id:
            raise DecisionRouteViolation("tenant_id is required")
        if not user_id:
            raise DecisionRouteViolation("user_id is required")
        observation = observer.observe(
            tenant_id=tenant_id,
            metrics=dict(body.get("metrics") or {}),
            context={
                "decision_id": route.decision_id,
                "correlation_id": route.correlation_id,
                "issuer_id": route.issuer_id,
            },
        )
    except DecisionRouteViolation as exc:
        return _blocked(
            payload=body,
            effects=effects,
            decision_id=route.decision_id,
            correlation_id=route.correlation_id,
            reason="route_violation",
            exc=exc,
        )

    reward_value = (
        observation.get("reward")
        if isinstance(observation, Mapping)
        else None
    )
    delivery = effects.send_message(
        decision_id=route.decision_id,
        correlation_id=route.correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        text=f"📈 Reward observed: {reward_value}",
        track_event_type=ACTION_NAME,
        track_payload={"tenant_id": tenant_id, "reward": reward_value},
        channel=str(body.get("channel") or "telegram"),
        channel_policy=(
            dict(body.get("channel_policy") or {})
            if isinstance(body.get("channel_policy"), Mapping)
            else None
        ),
    )
    evidence = _delivery_evidence(delivery)
    delivery_ok = bool(delivery.get("ok")) if isinstance(delivery, Mapping) else bool(delivery)
    verified = bool(delivery_ok and evidence)
    return {
        "ok": verified,
        "status": "verified" if verified else "failed",
        "observation": observation,
        "delivery": delivery,
        "router_evidence": evidence if verified else None,
    }
