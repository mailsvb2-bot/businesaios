from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime.actions import ACTION_GROWTH_PROPOSE_V1
from runtime.decisioning import DecisionRouteViolation, extract_strict_route_from_envelope
from runtime.handlers.growth_strategy_generate import handle_growth_strategy_generate
from runtime.handlers.route_failure_support import (
    best_effort_route_ids,
    blocked_error_payload,
    safe_route_blocked_text,
)
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True
ACTION_NAME = ACTION_GROWTH_PROPOSE_V1
_LEGACY_SIGNAL_FIELDS = ("conversion_rate", "roas")


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


def _canonical_goal(body: Mapping[str, Any]) -> dict[str, Any]:
    goal = (
        dict(body.get("goal") or {})
        if isinstance(body.get("goal"), Mapping)
        else {}
    )
    constraints = [
        str(item).strip()
        for item in (goal.get("constraints") or ())
        if str(item).strip()
    ]
    objective = str(body.get("objective") or "growth").strip()
    if objective:
        constraints.append(f"objective:{objective[:200]}")

    signals = (
        dict(body.get("signals") or {})
        if isinstance(body.get("signals"), Mapping)
        else {}
    )
    for field in _LEGACY_SIGNAL_FIELDS:
        if field not in signals:
            continue
        try:
            value = float(signals[field])
        except (TypeError, ValueError):
            continue
        constraints.append(f"signal:{field}={value:.6g}")

    goal["constraints"] = tuple(dict.fromkeys(constraints))
    return goal


def handle_growth_propose(
    payload: dict[str, Any],
    effects: EffectsPort,
    env: Any,
    *,
    event_store: Any,
    llm: Any = None,
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

    try:
        tenant_id = str(body.get("tenant_id") or "").strip()
        user_id = str(body.get("user_id") or "").strip()
        if not tenant_id:
            raise DecisionRouteViolation("tenant_id is required")
        if not user_id:
            raise DecisionRouteViolation("user_id is required")
        if event_store is None:
            raise RuntimeError("canonical event store is unavailable")

        canonical_payload = dict(body)
        canonical_payload["tenant_id"] = tenant_id
        canonical_payload["user_id"] = user_id
        canonical_payload["goal"] = _canonical_goal(body)
        result = handle_growth_strategy_generate(
            canonical_payload,
            effects,
            env,
            event_store=event_store,
            llm=llm,
            track_event_type=ACTION_NAME,
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
    except Exception as exc:
        return _blocked(
            payload=body,
            effects=effects,
            decision_id=route.decision_id,
            correlation_id=route.correlation_id,
            reason="canonical_growth_failed",
            exc=exc,
        )

    if not isinstance(result, Mapping):
        return result
    outcome = dict(result)
    plan = outcome.get("plan")
    hypotheses = getattr(plan, "top_hypotheses", ()) if plan is not None else ()
    outcome["queued"] = len(tuple(hypotheses or ()))
    outcome["compatibility_action"] = ACTION_NAME
    return outcome
