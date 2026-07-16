"""Ads apply execution handler (runtime).

This is an effect handler: it executes an already-decided AdsPlan via the
production-hard core.ads.apply_engine.AdsApplyEngine.

No business decisions here.
"""

from __future__ import annotations

from typing import Any

from runtime.ads import AdsApplyEngine, bind_runtime_state, maturity_gate
from runtime.governance import ActuationRegistry
from runtime.handlers.ads_apply_evidence import attach_ads_apply_outcome
from runtime.handlers.delivery_contract import delivery_kwargs
from runtime.handlers.ads_apply_helpers import (
    build_apply_request,
    emit_apply_audit,
    emit_apply_success_governance,
    summary_text,
)
from runtime.handlers.ads_apply_route import AutopilotApplyRouteViolation, extract_ads_apply_route
from runtime.handlers.route_failure_support import (
    best_effort_route_ids as _best_effort_route_ids,
)
from runtime.handlers.route_failure_support import (
    blocked_error_payload,
    safe_route_blocked_text,
)
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True
ACTION_NAME = "ads_apply_execute@v1"


def _blocked_notification(
    *,
    effects: EffectsPort,
    decision_id: str,
    correlation_id: str,
    tenant_id: str,
    user_id: str,
    payload: dict[str, Any],
    text: str,
    **kwargs: Any,
) -> dict[str, Any]:
    notification = effects.send_message(
        decision_id=decision_id,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        text=text,
        **delivery_kwargs(payload),
        **kwargs,
    )
    return attach_ads_apply_outcome(
        notification=notification,
        status="blocked",
        detail={"reason": "pre_apply_blocked"},
    )


def handle_ads_apply_execute(
    payload: dict[str, Any],
    effects: EffectsPort,
    env: Any,
    *,
    engine: AdsApplyEngine | None,
    event_store: Any | None = None,
) -> Any:
    ActuationRegistry.register(
        domain="ads.apply",
        controller_id=ACTION_NAME,
        source=__file__,
    )
    ActuationRegistry.assert_single_executor(domain="ads.apply")

    body = dict(payload or {})
    tenant_id = str(body.get("tenant_id") or "").strip()
    user_id = str(body.get("user_id") or "").strip()
    if not tenant_id:
        raise RuntimeError("TENANT_ID_REQUIRED")
    if not user_id:
        raise RuntimeError("USER_ID_REQUIRED")
    try:
        route = extract_ads_apply_route(payload=body, env=env)
    except AutopilotApplyRouteViolation as exc:
        fallback_decision_id, fallback_correlation_id = _best_effort_route_ids(
            payload=body,
            env=env,
        )
        return _blocked_notification(
            effects=effects,
            decision_id=fallback_decision_id,
            correlation_id=fallback_correlation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            payload=body,
            text=safe_route_blocked_text("Ads Apply"),
            callback_query_id=body.get("callback_query_id"),
            track_event_type="ads_apply_execute_blocked@v1",
            track_payload=blocked_error_payload(
                reason="route_violation",
                exc=exc,
            ),
        )
    bind_runtime_state(event_store=event_store)
    if engine is None:
        raise RuntimeError("boot failure: Ads Apply engine must be wired before handler dispatch")
    idem_key = str(body.get("idempotency_key") or "")
    if not idem_key.strip():
        return _blocked_notification(
            effects=effects,
            decision_id=route.decision_id,
            correlation_id=route.correlation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            payload=body,
            text="❌ Нужен Idempotency-Key для Ads Apply (защита от повторов). Повтори действие из UI.",
        )
    request, gate_state, request_tenant_id, user_id = build_apply_request(body)
    if str(request_tenant_id) != tenant_id:
        raise RuntimeError("TENANT_CONTEXT_MISMATCH:ads_apply_request")
    result = engine.execute(req=request, gate_state=gate_state)

    if isinstance(result.audit_event, dict):
        try:
            emit_apply_audit(
                effects=effects,
                payload=body,
                user_id=user_id,
                audit_event=result.audit_event,
            )
        except Exception as exc:
            effects.track_event(
                decision_id=route.decision_id,
                correlation_id=route.correlation_id,
                user_id=user_id,
                event_type="ads_apply_audit_emit_failed@v1",
                payload={
                    "tenant_id": tenant_id,
                    "error": exc.__class__.__name__,
                },
                source="ads",
            )

    if result.status == "applied":
        try:
            maturity_gate.mark_executed(
                tenant_id=tenant_id,
                decision_id=route.decision_id,
            )
        except Exception as exc:
            effects.track_event(
                decision_id=route.decision_id,
                correlation_id=route.correlation_id,
                user_id=user_id,
                event_type="ads_apply_maturity_mark_failed@v1",
                payload={
                    "tenant_id": tenant_id,
                    "error": exc.__class__.__name__,
                },
                source="governance",
            )
        try:
            emit_apply_success_governance(
                effects=effects,
                payload=body,
                user_id=user_id,
            )
        except Exception as exc:
            effects.track_event(
                decision_id=route.decision_id,
                correlation_id=route.correlation_id,
                user_id=user_id,
                event_type="ads_apply_decision_executed_emit_failed@v1",
                payload={
                    "tenant_id": tenant_id,
                    "error": exc.__class__.__name__,
                },
                source="governance",
            )

    summary = summary_text(status=result.status, detail=result.detail)
    notification = effects.send_message(
        decision_id=route.decision_id,
        correlation_id=route.correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        text=summary,
        callback_query_id=body.get("callback_query_id"),
        track_event_type="ads_apply_executed@v1",
        track_payload={
            "tenant_id": tenant_id,
            "status": result.status,
        },
        **delivery_kwargs(body),
    )
    return attach_ads_apply_outcome(
        notification=notification,
        status=result.status,
        detail=result.detail,
    )
