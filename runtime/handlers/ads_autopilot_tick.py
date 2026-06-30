from __future__ import annotations

from typing import Any
from runtime.governance import PolicyUpdateGateError
from runtime.handlers.ads_autopilot_flow import (
    AutopilotRouteViolation,
    ensure_autopilot_gate,
    extract_autopilot_route,
    format_autopilot_result,
    gate_error_text,
)
from runtime.handlers.ads_autopilot_tick_parts.engine_contract import AdsAutopilotTickContractViolation
from runtime.handlers.ads_autopilot_tick_parts.messages import send_autopilot_message
from runtime.handlers.ads_autopilot_tick_parts.request_factory import build_safe_autopilot_request
from runtime.handlers.ads_autopilot_tick_parts.runner import execute_autopilot_tick
from runtime.handlers.route_failure_support import (
    best_effort_route_ids,
    blocked_error_payload,
    safe_route_blocked_text,
    safe_runtime_error_text,
)
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True
ACTION_NAME = 'ads_autopilot_tick@v1'

def handle_ads_autopilot_tick(
    payload: dict[str, Any],
    effects: EffectsPort,
    env: Any,
    *,
    engine: Any,
    event_store: Any | None = None,
) -> Any:
    p = payload or {}

    try:
        route = extract_autopilot_route(payload=p, env=env)
    except AutopilotRouteViolation as exc:
        return send_autopilot_message(
            effects=effects,
            payload=p,
            decision_id=best_effort_route_ids(payload=p, env=env)[0],
            correlation_id=best_effort_route_ids(payload=p, env=env)[1],
            text=safe_route_blocked_text('Ads Autopilot'),
            track_event_type='ads_autopilot_tick_blocked@v1',
            track_payload=blocked_error_payload(reason='route_violation', exc=exc),
        )

    _tenant_id, gate_error = ensure_autopilot_gate(payload=p, event_store=event_store, route=route)
    if gate_error is not None:
        return send_autopilot_message(
            effects=effects,
            payload=p,
            decision_id=route.decision_id,
            correlation_id=route.correlation_id,
            text=gate_error_text(gate_error),
            track_event_type='ads_autopilot_tick_blocked@v1',
            track_payload={'reason': 'gate_blocked', 'error': str(gate_error)},
        )

    try:
        req = build_safe_autopilot_request(payload=p, route=route)
        res = execute_autopilot_tick(engine=engine, req=req)
        return send_autopilot_message(
            effects=effects,
            payload=p,
            decision_id=route.decision_id,
            correlation_id=route.correlation_id,
            text=format_autopilot_result(res),
            track_event_type=ACTION_NAME,
            track_payload={'status': getattr(res, 'status', 'ok')},
        )
    except (AdsAutopilotTickContractViolation, PolicyUpdateGateError, ValueError) as exc:
        return send_autopilot_message(
            effects=effects,
            payload=p,
            decision_id=route.decision_id,
            correlation_id=route.correlation_id,
            text='🛑 Ads Autopilot blocked by policy or contract.',
            track_event_type='ads_autopilot_tick_blocked@v1',
            track_payload=blocked_error_payload(reason='contract_or_policy', exc=exc),
        )
    except Exception as exc:
        return send_autopilot_message(
            effects=effects,
            payload=p,
            decision_id=route.decision_id,
            correlation_id=route.correlation_id,
            text=safe_runtime_error_text('Ads Autopilot'),
            track_event_type='ads_autopilot_tick_error@v1',
            track_payload=blocked_error_payload(reason='runtime_error', exc=exc),
        )
