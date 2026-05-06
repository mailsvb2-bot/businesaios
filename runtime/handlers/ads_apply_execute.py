from __future__ import annotations

CANON_THIN_HANDLER = True


"""Ads apply execution handler (runtime).

This is an effect handler: it executes an already-decided AdsPlan via the
production-hard core.ads.apply_engine.AdsApplyEngine.

No business decisions here.
"""

from typing import Any, Dict

from runtime.ports.effects import EffectsPort

from runtime.ads import AdsApplyEngine, bind_runtime_state, maturity_gate
from runtime.governance import ActuationRegistry
from runtime.handlers.ads_apply_helpers import (
    build_apply_request,
    emit_apply_audit,
    emit_apply_success_governance,
    summary_text,
)
from runtime.handlers.ads_apply_route import AutopilotApplyRouteViolation, extract_ads_apply_route
from runtime.handlers.route_failure_support import (
    best_effort_route_ids as _best_effort_route_ids,
    blocked_error_payload,
    safe_route_blocked_text,
)

ACTION_NAME = "ads_apply_execute@v1"



def handle_ads_apply_execute(payload: Dict[str, Any], effects: EffectsPort, env: Any, *, engine: AdsApplyEngine | None, event_store: Any | None = None) -> Any:
    ActuationRegistry.register(domain="ads.apply", controller_id=ACTION_NAME, source=__file__)
    ActuationRegistry.assert_single_executor(domain="ads.apply")

    p = payload or {}
    try:
        route = extract_ads_apply_route(payload=p, env=env)
    except AutopilotApplyRouteViolation as exc:
        fallback_decision_id, fallback_correlation_id = _best_effort_route_ids(payload=p, env=env)
        return effects.send_message(
            decision_id=fallback_decision_id,
            correlation_id=fallback_correlation_id,
            user_id=str(p.get("user_id") or ""),
            text=safe_route_blocked_text("Ads Apply"),
            callback_query_id=p.get("callback_query_id"),
            track_event_type="ads_apply_execute_blocked@v1",
            track_payload=blocked_error_payload(reason="route_violation", exc=exc),
        )
    bind_runtime_state(event_store=event_store)
    if engine is None:
        raise RuntimeError("boot failure: Ads Apply engine must be wired before handler dispatch")
    user_id = str(p.get("user_id") or "")
    idem_key = str(p.get("idempotency_key") or "")
    if not idem_key.strip():
        return effects.send_message(
            decision_id=route.decision_id,
            correlation_id=route.correlation_id,
            user_id=str(p.get("user_id") or ""),
            chat_id=str(p.get("chat_id") or ""),
            text="❌ Нужен Idempotency-Key для Ads Apply (защита от повторов). Повтори действие из UI.",
        )
    req, gate_state, _tenant_id, user_id = build_apply_request(p)
    res = engine.execute(req=req, gate_state=gate_state)

    if isinstance(res.audit_event, dict):
        try:
            emit_apply_audit(effects=effects, payload=p, user_id=user_id, audit_event=res.audit_event)
        except Exception as exc:
            effects.track_event(
                decision_id=route.decision_id,
                correlation_id=route.correlation_id,
                user_id=user_id,
                event_type="ads_apply_audit_emit_failed@v1",
                payload={"error": exc.__class__.__name__},
                source="ads",
            )

    if res.status == "applied":
        try:
            maturity_gate.mark_executed(tenant_id=str(_tenant_id), decision_id=route.decision_id)
        except Exception as exc:
            effects.track_event(
                decision_id=route.decision_id,
                correlation_id=route.correlation_id,
                user_id=user_id,
                event_type="ads_apply_maturity_mark_failed@v1",
                payload={"error": exc.__class__.__name__},
                source="governance",
            )
        try:
            emit_apply_success_governance(effects=effects, payload=p, user_id=user_id)
        except Exception as exc:
            effects.track_event(
                decision_id=route.decision_id,
                correlation_id=route.correlation_id,
                user_id=user_id,
                event_type="ads_apply_decision_executed_emit_failed@v1",
                payload={"error": exc.__class__.__name__},
                source="governance",
            )

    summary = summary_text(status=res.status, detail=res.detail)
    return effects.send_message(
        decision_id=route.decision_id,
        correlation_id=route.correlation_id,
        user_id=user_id,
        text=summary,
        callback_query_id=p.get("callback_query_id"),
        track_event_type="ads_apply_executed@v1",
        track_payload={"status": res.status},
    )
