from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime.actions import ACTION_GROWTH_PROPOSE_V1
from runtime.decisioning import DecisionRouteViolation, extract_strict_route_from_envelope
from runtime.handlers.route_failure_support import (
    best_effort_route_ids,
    blocked_error_payload,
    safe_route_blocked_text,
)
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True
ACTION_NAME = ACTION_GROWTH_PROPOSE_V1


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
        text=safe_route_blocked_text("Growth propose"),
        track_event_type="growth_propose_blocked@v1",
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


def handle_growth_propose(
    payload: dict[str, Any],
    effects: EffectsPort,
    env: Any,
    *,
    proposal_service: Any,
    proposal_gateway: Any,
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

    if proposal_service is None or proposal_gateway is None:
        raise RuntimeError(
            "boot failure: growth proposal service and gateway must be wired before handler dispatch"
        )

    try:
        tenant_id = str(body.get("tenant_id") or "").strip()
        user_id = str(body.get("user_id") or "").strip()
        if not tenant_id:
            raise DecisionRouteViolation("tenant_id is required")
        if not user_id:
            raise DecisionRouteViolation("user_id is required")
        proposals = proposal_service.build_proposals(
            tenant_id=tenant_id,
            objective=str(body.get("objective") or "growth").strip(),
            signals=dict(body.get("signals") or {}),
        )
        queued = proposal_service.queue(
            gateway=proposal_gateway,
            tenant_id=tenant_id,
            decision_id=route.decision_id,
            correlation_id=route.correlation_id,
            issuer_id=route.issuer_id,
            proposals=proposals,
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

    delivery = effects.send_message(
        decision_id=route.decision_id,
        correlation_id=route.correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        text=f"📦 Growth proposals queued: {queued}",
        track_event_type=ACTION_NAME,
        track_payload={"tenant_id": tenant_id, "queued": queued},
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
        "queued": queued,
        "delivery": delivery,
        "router_evidence": evidence if verified else None,
    }
