from __future__ import annotations

import time
from typing import Any

from core.behavior.behavioral_state_builder import BehavioralStateBuilder
from core.behavior.constraints import price_constraints_from_behavior
from core.telemetry.behavioral import BehaviorTelemetryV1
from core.tenancy.request_context import bind_tenant, get_tenant_id
from interfaces.telegram.pipeline.enrichment_step import build_economy
from interfaces.telegram.pipeline.tenant_resolution import resolve_tenant_for_update
from interfaces.telegram.pipeline.worldstate_step import build_worldstate
from interfaces.telegram.runtime.telegram_runtime_worldstate_builder import apply_telegram_overlays


def build_button_key(ctx: Any) -> str | None:
    try:
        if bool(getattr(ctx, "is_callback", False)) and getattr(ctx, "callback_data", None):
            return f"cb:{str(ctx.callback_data)[:64]}"
        if getattr(ctx, "command", None):
            return f"cmd:{str(ctx.command)[:64]}"
        if getattr(ctx, "text", None):
            return f"txt:{str(ctx.text)[:64]}"
    except Exception:
        return None
    return None


def resolve_product_context(*, resolver: Any, ctx: Any, enrich: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        resolved = resolver.resolve(
            command=getattr(ctx, "command", None),
            args=str(getattr(ctx, "args", "") or ""),
            user_settings=(enrich.get("settings") or {}) if isinstance(enrich.get("settings"), dict) else {},
        )
        if resolved:
            return dict(resolved)
    except Exception:
        return dict(fallback or {})
    return dict(fallback or {})


def build_worldstate_with_overlays(*, event_log: Any, ctx: Any, enrich: dict[str, Any], resolved_product: dict[str, Any], behavior_builder: BehavioralStateBuilder, now_ms: int) -> Any:
    _ = build_economy(enrich=enrich)
    tenant_id = resolve_tenant_for_update(chat_id=str(ctx.chat_id), user_id=str(ctx.chat_id), text=str(ctx.text))
    bind_tenant(tenant_id)
    ws = build_worldstate(
        event_log=event_log,
        ctx=ctx,
        tenant_id=tenant_id,
        enrich=enrich,
        resolved_product=resolved_product,
        now_ms=now_ms,
    )
    behavioral_state = behavior_builder.build_from_readmodel(
        {
            "entitlements": enrich.get("entitlements") or {},
            "payments": enrich.get("payments") or {},
            "fatigue_index": (enrich.get("realtime_state") or {}).get("fatigue_index") if isinstance(enrich.get("realtime_state"), dict) else None,
            "trust_index": (enrich.get("realtime_state") or {}).get("trust_index") if isinstance(enrich.get("realtime_state"), dict) else None,
        },
        product=ws.product if isinstance(ws.product, dict) else resolved_product,
        tenant_id=str(ws.tenant_id or get_tenant_id() or "default"),
        safe_mode=bool(ws.safe_mode),
    )
    behavior_payload = (enrich.get("behavior") or {}) if isinstance(enrich.get("behavior"), dict) else {}
    if bool(ws.safe_mode) and bool(behavioral_state.get("guardrails_violation")):
        behavior_payload = {**behavior_payload, "guardrails_violation": True}
    return apply_telegram_overlays(
        ws,
        user_patch={
            "settings": enrich.get("settings") or {},
            "city": enrich.get("city") or "",
            "selected_tariff": enrich.get("selected_tariff"),
            "mood_last": enrich.get("mood_last") or [],
            "admin_metrics": enrich.get("admin_metrics") or {"users_today": 0},
            "roles": enrich.get("roles") or [],
            "perms": enrich.get("perms") or [],
            "is_superadmin": bool(enrich.get("is_superadmin")),
            "marketing_variants": enrich.get("marketing_variants") or {},
            "marketing_seed": enrich.get("marketing_seed") or "1",
        },
        behavior_patch=behavior_payload,
        behavioral_state=behavioral_state,
        price_constraints=price_constraints_from_behavior(
            behavior=behavior_payload,
            product=ws.product if isinstance(ws.product, dict) else {},
        ),
    )


def emit_behavior_telemetry(*, event_log: Any, ctx: Any, ws: Any) -> None:
    now_ms = int(time.time() * 1000)
    kind = "callback" if bool(getattr(ctx, "is_callback", False)) else "message"
    button_id = None
    if bool(getattr(ctx, "is_callback", False)) and getattr(ctx, "callback_data", None):
        button_id = str(ctx.callback_data)[:128]
    elif getattr(ctx, "command", None):
        button_id = str(ctx.command)[:128]
    tel = BehaviorTelemetryV1(
        user_id=str(ws.user_id or ctx.chat_id),
        tenant_id=str(ws.tenant_id or "default"),
        ts_ms=now_ms,
        kind=str(kind),
        button_id=button_id,
        screen="telegram",
    )
    event_log.emit(
        event_type="behavior_telemetry",
        source="telegram",
        user_id=str(ws.user_id or ctx.chat_id),
        decision_id="-",
        correlation_id=str((ws.meta or {}).get("correlation_key") or "-"),
        payload=tel.to_event_payload(),
    )


def run_decision_and_execution(*, event_log: Any, ctx: Any, ws: Any, button_key: str | None, decide_fn: Any, execute_fn: Any) -> None:
    from core.observability.perf import Span

    with event_log.batch():
        ck = str((ws.meta or {}).get("correlation_key") or "")
        with Span(
            event_log=event_log,
            stage="decide",
            user_id=str(ws.user_id),
            correlation_key=ck,
            extra={"update_id": int(ctx.update_id), "button_key": button_key, "callback_data": ctx.callback_data, "command": ctx.command},
        ):
            env = decide_fn(ws)
        with Span(
            event_log=event_log,
            stage="execute",
            user_id=str(ws.user_id),
            correlation_key=ck,
            extra={"action": getattr(getattr(env, "decision", None), "action", None), "button_key": button_key},
        ):
            execute_fn(env)
